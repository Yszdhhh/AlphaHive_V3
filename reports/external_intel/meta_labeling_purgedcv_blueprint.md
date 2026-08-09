# Meta-Labeling Purged CV 实现蓝图（可照抄）

- 生成：2026-08-08 UTC
- 性质：技术落地蓝图（对应 `meta_labeling_plan.md` §3.3/§5.4 的代码级实现）
- 配套：`meta_labeling_features_inventory.md`（特征字段级清单）
- 适用范围：wash_cvd 事件池（115 口径，n=1348，2022-01→2026-06，72h 冷却），标签 r168−54bps>0，标签窗 168h
- 关键前提：**冷却 72h < 标签窗 168h → 相邻事件标签重叠 96h 真实存在**，naive k-fold 必然泄漏，必须 purge + embargo

---

## 0. 判定锚（预注册，照抄 plan §3.4）

| 门槛 | 值 |
|---|---|
| 模型质量 | purged OOF AUC > **0.55**（≤0.55 直接判死） |
| 增量（核心） | meta 过滤后 168h 超额 **≥ 锚基线 + 1.0pp**，且 bootstrap CI 下界 > 0 |
| 锚基线（预注册二选一，不可事后换） | 主口径（n=1348 全事件）：复算 V_ref 基线超额；对照口径：V_confirm（792）基线 +3.56% |
| 样本 | 过滤后 n ≥ 30 |
| 稳健性 | 尾切不转负；W1/W2 方向一致；0.5×/1×/2× 成本敏感性净期望仍正 |
| 证伪 | OOF AUC ≤ 0.55，或增量 CI 跨零，或 W1/W2 不一致 → 关闭并记录 |
| trials | 阈值扫描次数 + 超参组合全部记账（见 §9） |

**第 0 步（不可跳过）**：先复算基线（V_ref / V_confirm 的 168h 均值、超额、CI）。复算对不上 → 停止，不进入建模。

---

## 1. 数据契约（事件宽表 schema）

建模输入一张宽表，每行一个事件，全部特征 asof 事件时点：

```
events = DataFrame(
    symbol    : str      # 币种
    ts        : int64    # 事件时点（ms UTC，115 detect_events 输出）
    r168      : float    # (close[t+168h]/close[t] − 1) × 100   ← 148 口径 pos+168
    r4        : float    # (close[t+4h]/close[t] − 1) × 100     ← 主口径下作为特征
    y         : int      # 1[r168 > 0.54]（0.54 = 双边成本 27bps×2，QUANT_METHODOLOGY §4.1）
    <特征列>   : float    # 见 features_inventory.md，全部事件时点 asof
)
```

**时点语义（预注册，关键）**：
- 标签锚定事件 ts：`y = 1[r168 > 0.54]`，r168 从事件 ts 起算（与 148/157/160 完全同口径）。
- r4 是**事件后 4h 才知道**的特征（确认信息）：主口径 = 全部 1348 事件建模、r4 作特征，模型自己学"4h 确认是否值得"；不手工切 V_confirm 子集。
- purge/embargo 的标签窗一律 = `[ts, ts + 168h]`，与 r4 何时可得的入场时点无关（保守口径，标签窗覆盖事件后全部信息）。

**前置检查**：`n == 1348`、`y 正类率 ∈ [0.40, 0.55]`、无重复 (symbol, ts)、ts 已排序副本用于切块。

---

## 2. 总流程

```
1. 拼宽表（复用 148/157/160/161/164 的函数，见 features_inventory.md §6 代码模板）
2. asof 审计：每列人工过"事件时点是否已知"（np_z/cycle_z 滚动口径，见 §12 错误清单 #8/#9）
3. 复算基线（§0 第 0 步）
4. 主循环：k=5 时间有序 purged k-fold
     每 fold：train_keep = purge(train) ∩ embargo(train)   ← 先 purge 再 embargo
              fit scaler/imputer 只用 train_keep；fit 模型；预测该 fold 测试块
      收集 OOF 概率 p、OOF 真值 y、OOF r168、OOF symbol/ts
5. OOF 汇总：pooled AUC + 每 fold AUC；校准曲线；Brier/ECE
6. T 扫描（仅 OOF）：T ∈ {0.50,0.55,0.60,0.65,0.70,0.75}，选净期望最大且 n≥30 者；trials 记账
7. bootstrap CI（symbol 聚类）：AUC CI + 增量 CI（选 T 后过滤 vs 锚基线）
8. 对照判定（§0）→ GO / NO_GO
9. （确认手段）walk-forward 滚动复跑（§10）
```

---

## 3. purged k-fold 构造：时间有序切块

按事件 ts 全局排序后切 k 个**连续时间块**（不随机、不按 symbol 分层）。同一 ts 的跨币事件（washout 常多币并发）天然落在同一块 → 截面相关不会跨 fold 泄漏。

```python
def time_ordered_folds(events: pd.DataFrame, k: int = 5) -> list[np.ndarray]:
    """返回 k 个索引数组（每个 = 该 fold 测试块的事件行号）。

    按 ts 稳定排序后切连续块；块大小按事件数均分（时间有序的等容量块）。
    """
    ts = events["ts"].to_numpy(dtype=np.int64)
    order = np.argsort(ts, kind="stable")
    edges = np.array_split(np.arange(len(events)), k)   # 行号（未排序语义下的位置）
    folds = []
    for e in edges:
        folds.append(order[e])                          # 每个块内 ts 升序
    # 断言：块间时间不重叠（同一 ts 跨币事件不会拆到两块）
    for i in range(k - 1):
        assert ts[folds[i]].max() <= ts[folds[i + 1]].min()
    return folds
```

> 注：等容量块 vs 等时间块——选等容量（每 fold 测试集 ~270 事件，统计功效均衡）。时间跨度不均没关系，purge/embargo 只关心边界。

---

## 4. purge 精确算法

**定义**：测试块区间 `[t_start, t_end]`（块内最早/最晚事件 ts）。训练集任一事件 `i` 的标签窗为 `[ts_i, ts_i + LABEL_MS]`。若该窗与测试块重叠（`ts_i + LABEL_MS > t_start`），则 `i` 的标签"看过"测试块信息 → 从该 fold 训练集**剔除**。

```python
LABEL_MS = 168 * 3_600_000      # 标签窗 = 168h
EMBARGO_MS = 168 * 3_600_000    # embargo = 168h（≥ 标签窗，见 §5）

def purge_and_embargo(ts: np.ndarray, test_idx: np.ndarray,
                      label_ms: int = LABEL_MS,
                      embargo_ms: int = EMBARGO_MS) -> np.ndarray:
    """给定全量事件 ts 与该 fold 测试块索引，返回该 fold 可用训练索引。

    purge   ：训练事件标签窗 [ts, ts+label_ms] 与测试块重叠 → 剔除
               （即 ts + label_ms > t_start，等价于 ts > t_start − label_ms 的事件被剔）
    embargo ：测试块之后 [t_end, t_end + embargo_ms) 内的训练事件 → 剔除
               （吸收测试块到后续训练样本之间的自相关/波动聚集残余依赖）
    """
    t_start = ts[test_idx].min()
    t_end = ts[test_idx].max()
    train_idx = np.setdiff1d(np.arange(len(ts)), test_idx)

    # ---- purge：只作用于测试块之前的事件（之后事件的标签窗整体在测试块之后，无重叠）----
    before = ts[train_idx] <= t_start
    keep = train_idx[before & (ts[train_idx] + label_ms <= t_start)]

    # ---- embargo：测试块之后的事件，剔除落在 (t_end, t_end+embargo_ms] 内的 ----
    after_keep = train_idx[ts[train_idx] > t_end]
    after_keep = after_keep[ts[after_keep] > t_end + embargo_ms]
    return np.concatenate([keep, after_keep])
```

**为什么 purge 只剔"之前"的事件**：测试块之后的事件 `ts > t_end`，其标签窗 `[ts, ts+168h]` 整体在测试块之后，不会"回看"测试块；它们的特征也不含测试块信息（特征全部 asof 自己时点之前）。需要防的是**测试块之后紧邻一段时间的序列自相关**——这正是 embargo 的职责。

**边界严格性**：`ts + label_ms <= t_start` 保留（严格不重叠）；`ts + label_ms > t_start` 剔除。边界事件落在哪块由排序稳定 + 块内索引唯一决定，无二义。

**期望损耗（可预期，不必惊讶）**：全样本跨度 ~1641 天 / 1348 事件 ≈ 0.82 事件/天。每 fold 边界 purge 掉 ~7 天 ≈ 6 事件、embargo 掉 ~7 天 ≈ 6 事件（首末 fold 只一侧）。k=5 时每个训练集约丢 12/1080 ≈ 1%，**远小于泄漏代价**。

---

## 5. embargo 细节

- **量**：`EMBARGO_MS = 168h = 标签窗`。AFML 建议 embargo ≥ 标签水平（防自相关标签残留）；本方案直接取等长 168h，满足 plan §3.3"embargo ≥ 168h"。
- **方向**：只取测试块**之后**的缓冲（时间只向前流动；测试块之前的事件已由 purge 管重叠、由"特征 asof 自身时点"保证无未来信息）。
- **与 purge 的顺序**：先 purge 再 embargo（两者独立，顺序不影响结果，但代码上先 purge 得到"无标签重叠集"、再 embargo 是语义清晰的读法）。
- **首 fold**：测试块最早，无"之前"事件可 purge，embargo 丢测试块之后 7 天 → 正确（训练集是后来的数据）。
- **末 fold**：embargo 之后的集合为空 → 自然无操作。
- **绝不做**：embargo < 168h；只对相邻 fold 做 embargo（每一 fold 都必须用自己的边界独立计算）。

---

## 6. 跨 symbol 截面事件

- washout/wash_cvd 在 BTC 崩盘/瀑布语境下**多币并发**（2022 LUNA/FTX、2024/2025 崩盘），不同币同一小时同时触发。若随机行切分，同一时点的截面事件会散进 train/test → 测试块"见过"并发信息。
- 本方案时间块切分天然解决：**同一 ts 的所有币事件在同一块**（§3 断言已保证）。purge/embargo 用 ts 判定，与 symbol 无关，天然正确。
- **不要**做 symbol 分层采样、不要 GroupKFold(symbol)（会把同币不同时期的事件拆到 train/test，与"截面相关"目标错位——本实验要防的是**时点**相关，不是币种 id 相关）。
- bootstrap 阶段再按 symbol 聚类（§8），那是 CI 的口径问题，与 fold 构造无关。

---

## 7. 训练循环（L1 logistic + 浅 GBM）

```python
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

FEATURES = [...]          # 见 features_inventory.md §1 总表（建议先 10~12 列，强正则化）
C_L1 = 1.0                # 预注册；若扫 C → 每个值记 1 个 trial
GBM_PARAMS = dict(max_depth=3, n_estimators=300, learning_rate=0.03,
                  min_samples_leaf=30, max_features=0.7, random_state=2026)

def fit_predict_train(X_tr, y_tr, X_te, model="l1"):
    """每 fold 内：imputer+scaler 只用训练集拟合（防泄漏），返回测试集概率。"""
    imp = SimpleImputer(strategy="median").fit(X_tr)
    X_tr_i, X_te_i = imp.transform(X_tr), imp.transform(X_te)
    if model == "l1":
        sc = StandardScaler().fit(X_tr_i)
        X_tr_s, X_te_s = sc.transform(X_tr_i), sc.transform(X_te_i)
        m = LogisticRegression(penalty="l1", solver="liblinear", C=C_L1, max_iter=2000)
        m.fit(X_tr_s, y_tr)
        return m.predict_proba(X_te_s)[:, 1]
    m = HistGradientBoostingClassifier(**GBM_PARAMS)
    m.fit(X_tr_i, y_tr)                    # HGB 原生支持 NaN，不再 impute 也可（二选一预注册）
    return m.predict_proba(X_te_i)[:, 1]

# ---- 主循环 ----
ts = events["ts"].to_numpy(dtype=np.int64)
X = events[FEATURES].to_numpy(dtype=float)
y = events["y"].to_numpy(dtype=int)
folds = time_ordered_folds(events, k=5)

oof_p = np.full(len(events), np.nan)
for test_idx in folds:
    train_idx = purge_and_embargo(ts, test_idx)
    p = fit_predict_train(X[train_idx], y[train_idx], X[test_idx], model="l1")
    oof_p[test_idx] = p
    print(f"fold test={len(test_idx)} train={len(train_idx)} "
          f"(purged+embargoed {len(events)-len(test_idx)-len(train_idx)}) "
          f"AUC={roc_auc_score(y[test_idx], p):.3f}")

ok = np.isfinite(oof_p)
auc = roc_auc_score(y[ok], oof_p[ok])
print(f"OOF pooled AUC = {auc:.3f}  (n={ok.sum()})")
events["p"] = oof_p     # OOF 概率（每个事件的预测来自没见过它的模型）
```

**要点**：
- 两种模型各跑一遍（l1 主、gbm 对照），OOF 各自独立；两个模型都判死才判死。
- 每 fold 内 `SimpleImputer/StandardScaler` 只用该 fold train_keep 拟合——**全量拟合是经典泄漏**（错误清单 #6）。
- 正类率 ~47-51%，接近平衡；**禁用随机过采样/欠采样改分布**（AFML：训练集须代表总体；且 purged CV 下重采样会把 purge 语义搞乱）。
- 若某 fold purge 后训练集 < 300 → 检查事件分布（2022 仅 92 事件，靠后 fold 训练集 ~1100，安全）。

---

## 8. 阈值 T 扫描（仅 OOF）+ trials 记账

```python
T_GRID = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
r168 = events["r168"].to_numpy(dtype=float)
ANCHOR = ...   # 预注册锚：主口径 = 全事件 168h 均值（复算）；对照口径 = V_confirm 均值

rows = []
for T in T_GRID:
    sel = (oof_p >= T) & np.isfinite(oof_p) & np.isfinite(r168)
    n = int(sel.sum())
    if n < 30:
        rows.append(dict(T=T, n=n, mean=np.nan, excess=np.nan))
        continue
    rows.append(dict(T=T, n=n, mean=r168[sel].mean(), excess=r168[sel].mean() - ANCHOR))

best = max([r for r in rows if r["n"] >= 30], key=lambda r: r["excess"], default=None)
print("T 扫描结果（trials 记账：", len(T_GRID), "个）:")
for r in rows:
    print(f"  T={r['T']:.2f} n={r['n']} mean={r['mean']:+.2f}% excess={r['excess']:+.2f}%")
```

**纪律**：
- T 只扫 OOF 概率。**绝不用**训练集概率或全样本重训后概率（否则 T 是"回看自己"挖出来的）。
- **T 扫描不能与模型选择共用同一份 OOF 二次挖掘**：模型超参在实验前预注册固定（§7 注释）；若必须调参，每次组合记 1 trial，且调参决策只能用"训练集内嵌套 CV"或干脆放弃该次 T 结果的显著性宣称。
- trials 记账表（预注册格式）：
  - 模型 A：L1 logistic（C=1.0 固定）→ 0 trial
  - 模型 B：浅 GBM（参数固定）→ 0 trial
  - T 扫描：6 个值 → 6 trials
  - 若事后补扫 T=0.525 之类 → 每补 1 个 +1 trial，**补出来的最优值必须按全部 trial 数做 deflated 处理（DSR 或 Bonferroni 阈值）**，否则不承认。
  - 总量写入 QUANT_PRE_REGISTRY（plan §3.4：消耗 1 个主问题配额）。

---

## 9. 校准曲线 + bootstrap CI

```python
from sklearn.calibration import calibration_curve

# ---- 校准曲线（OOF 上）----
fop, mpv = calibration_curve(y[ok], oof_p[ok], n_bins=10)
brier = float(np.mean((oof_p[ok] - y[ok]) ** 2))
ece = float(np.mean(np.abs(fop - mpv)))     # 近似 ECE（等权重 bin）
print(f"Brier={brier:.4f} ECE≈{ece:.4f}")
for b, (f_, m_) in enumerate(zip(fop, mpv)):
    print(f"  bin{b}: pred={m_:.3f} obs={f_:.3f}")

# ---- AUC 的 symbol 聚类 bootstrap CI（同币事件自相关 → 按币重采样）----
def boot_auc_ci(df: pd.DataFrame, n_boot: int = 1000, seed: int = 2026) -> tuple:
    rng = np.random.default_rng(seed)
    syms = np.unique(df["symbol"].to_numpy())
    aucs = []
    for _ in range(n_boot):
        bs = rng.choice(syms, size=len(syms), replace=True)
        idx = np.concatenate([np.flatnonzero(df["symbol"].to_numpy() == s) for s in bs])
        if len(np.unique(df["y"].to_numpy()[idx])) < 2:
            continue
        aucs.append(roc_auc_score(df["y"].to_numpy()[idx], df["p"].to_numpy()[idx]))
    lo, hi = np.percentile(aucs, [2.5, 97.5])
    return float(np.mean(aucs)), lo, hi

# ---- 选 T 后过滤事件的"增量 vs 锚" CI（同样是 symbol 聚类重采样）----
def boot_increment_ci(df_sel: pd.DataFrame, anchor: float,
                      n_boot: int = 1000, seed: int = 2027) -> tuple:
    """重采样（symbol 块）下 mean(r168_selected) − anchor 的 95% CI。"""
    rng = np.random.default_rng(seed)
    syms = np.unique(df_sel["symbol"].to_numpy())
    diffs = []
    for _ in range(n_boot):
        bs = rng.choice(syms, size=len(syms), replace=True)
        idx = np.concatenate([np.flatnonzero(df_sel["symbol"].to_numpy() == s) for s in bs])
        diffs.append(df_sel["r168"].to_numpy()[idx].mean() - anchor)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(np.mean(diffs)), lo, hi
```

**说明**：
- 为什么按 symbol 聚类：72h 冷却下同币事件相隔 ~3 天，168h 标签窗使同币相邻事件自相关；普通 i.i.d. bootstrap 的 CI 会**偏窄**（低估不确定性）。
- 增量 CI 的锚 `ANCHOR` 是常数（预注册基线均值），不是重采样量 → 重采样只作用于选中事件集。
- 尾切稳健性（gauntlet）：`sel_r[r <= np.quantile(sel_r, 0.95)].mean()` 不转负；成本敏感性：r168−0.27/0.54/1.08 三档净期望仍正。

---

## 10. walk-forward 滚动对照（最终确认手段）

```python
SPLITS = [
    ("2022-01-01", "2024-06-30", "2024-07-01", "2025-06-30"),   # 训练 → 验证
    ("2022-01-01", "2025-06-30", "2025-07-01", "2026-06-30"),
]
for tr0, tr1, va0, va1 in SPLITS:
    tr = events[(events["ts"] >= ms(tr0)) & (events["ts"] <= ms(tr1))]
    va = events[(events["ts"] >= ms(va0)) & (events["ts"] <= ms(va1))]
    # 注意：训练段尾部 168h 标签窗跨入验证段的训练事件也要 purge（同 §4 规则，以 va0 为 t_start）
    tr = tr[tr["ts"] + LABEL_MS <= ms(va0)]
    ...fit / predict / 记录验证段 AUC 与 T 过滤后均值...
```

- 与 purged CV 的结论要求**方向一致**；不一致 → 判死（§0 证伪条件）。

---

## 11. 常见错误清单（对照自查）

| # | 错误 | 后果 | 正确做法 |
|---|---|---|---|
| 1 | **purge 方向反**：从测试集里删行 | 泄漏原封不动 | purge 只作用于训练集（§4 代码） |
| 2 | **embargo < 标签窗**（如只留 72h=冷却窗） | 相邻 96h 重叠标签仍泄漏 | embargo ≥ 168h（本方案 = 168h） |
| 3 | **embargo 只做一次/只对相邻 fold** | 跨远 fold 的自相关未吸收 | 每 fold 用自己的 t_end 独立计算 |
| 4 | **随机 KFold / StratifiedKFold** | 并发截面事件散进 train/test | 时间有序切块（§3） |
| 5 | **同一 ts 的跨币事件被拆到两块** | 截面相关泄漏 | 按 ts 排序切块 + §3 断言 |
| 6 | **scaler/imputer 用全量拟合** | 测试分布信息进入训练 | 每 fold 内 train_keep 拟合（§7） |
| 7 | **阈值 T 用训练集/全样本概率扫** | T 过拟合、增量虚高 | 只扫 OOF（§8） |
| 8 | **cycle_z 用全期回归**（169 已警告：统计口径 vs 交易口径） | 特征含未来拟合 → 全实验级前视 | 交易口径滚动重算；或标注为受限特征并在结论里降权 |
| 9 | **np_z 等滚动特征用含未来的窗口** | 前视 | 只用 ≤ 事件时点的滚动窗（161 `rolling_z` 天然满足） |
| 10 | **r4 特征与标签时点错配**：r4 是 t+4h 才知，若误当"事件时点已知" | asof 违规 | 预注册：标签锚定 ts，r4 标记为 t+4h 已知（§1 时点语义） |
| 11 | **bootstrap 不按 symbol 聚类** | CI 偏窄、误判显著 | §9 聚类重采样 |
| 12 | **T 扫描与调参共用 OOF 二次挖掘** | 乐观偏误 | 超参预注册固定；补扫记 trials（§8） |
| 13 | **复算基线对不上还继续** | 锚失效，增量判定无意义 | 先复算（§0），对不上先停 |
| 14 | **purge 后某 fold 训练样本骤减不检查** | 高方差 fold 污染 pooled AUC | 打印每 fold train 大小，<300 报警（§7） |

---

## 12. 预注册模板（跑之前填好，随报告存档）

```yaml
meta_labeling_firstpass:
  event_pool: wash_cvd_115            # 2022-01→2026-06, 72h cooldown, n=1348
  label: "1[r168 > 0.54]"
  label_window_ms: 604800             # 168h
  embargo_ms: 604800                  # 168h
  cv: {method: purged_kfold, k: 5, block: time_ordered, per_fold: train_keep_only}
  models:
    l1:  {penalty: l1, solver: liblinear, C: 1.0}        # fixed, 0 trial
    gbm: {max_depth: 3, n_estimators: 300, lr: 0.03, min_samples_leaf: 30}  # fixed, 0 trial
  t_grid: [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]          # 6 trials
  anchor: <复算基线数值，预注册时固定>   # 主口径: V_ref 均值; 对照: V_confirm +3.56%
  gates: {auc_min: 0.55, increment_min_pp: 1.0, n_min: 30, ci_lo_gt_0: true}
  falsify: [auc_le_0.55, increment_ci_crosses_0, w1_w2_conflict]
  budget: "1 主问题配额 + trials 记账（见 QUANT_PRE_REGISTRY）"
```

---

## 13. 判定执行

```
if OOF AUC ≤ 0.55:                          → NO_GO，关闭并记录"规则层已捕获可用信息"
elif 最优 T 过滤后 n < 30:                  → 样本不足，不判定
elif 增量 CI 下界 > 0 且 ≥ +1.0pp 且尾切不转负 且 W1/W2 一致:
    → GO（预注册正式 ML alpha card，账户 E：meta 层）
else:                                       → NO_GO（附全部数字）
```
