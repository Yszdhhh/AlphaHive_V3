r"""125_cme_snapshot.py — CME 比特币/微型比特币机构持仓快照（一次性，非定时）。

命题背景：AlphaHive V3「大饼见底→山寨蓄力」研究（E 方向：新数据补充）。
CME 机构持仓（期货/期权未平仓合约与持仓变化）是「机构资金流」维度的免费可拉数据，
用于验证 wash_cvd 事件背后的机构参与度（120 宏观调制已收官，本数据作补充维度）。

接口：akshare crypto_bitcoin_cme(date='YYYYMMDD')
  - 返回列：商品 / 类型 / 电子交易合约 / 场内成交合约 / 场外成交合约 / 成交量 /
    未平仓合约 / 持仓变化
  - 商品：'比特币' / '微型比特币'；类型：期货 / 期权 / 看涨 / 看跌
  - 交易日才有数据（周末/节假日返回空）。
  - 实测（2026-08-07）：2026-08-06（周四）也返回空 → akshare 上游 CME 结算数据
    发布滞后约 1 个自然日，脚本对空结果容错跳过并计数。

用法：
  python scripts/125_cme_snapshot.py [--days 45] [--end YYYY-MM-DD] [--out PATH]
默认 --end = 北京时间今天（2026-08-07）。

输出：
  C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro\cme_bitcoin.parquet
  列：date, 商品, 类型, 电子交易合约, 场内成交合约, 场外成交合约, 成交量,
      未平仓合约, 持仓变化, source, pulled_at
  已存在时按 (date, 商品, 类型) 去重合并（幂等重跑安全）。

注意：
  - 一次性快照脚本，不做定时化（定时化需 Owner 签批，见 reports/new_data_plan.md T3 清单）。
  - 纯研究模块：只读外部数据、只写本 parquet，无订单路径、不写 live 配置。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

MACRO_ROOT = Path(r"C:\Users\10639\Desktop\🔒 加密资产\coinglass_db\macro")
OUT_PATH = MACRO_ROOT / "cme_bitcoin.parquet"
SOURCE = "akshare crypto_bitcoin_cme, https://akshare.akfamily.xyz/"
DEFAULT_DAYS = 45
NUMERIC_COLS = ["电子交易合约", "场内成交合约", "场外成交合约", "成交量", "未平仓合约", "持仓变化"]


def beijing_today() -> pd.Timestamp:
    """北京时间今天（Asia/Shanghai），归一化到无时区 date 语义。"""
    from zoneinfo import ZoneInfo

    return pd.Timestamp.now(tz=ZoneInfo("Asia/Shanghai")).tz_localize(None).normalize()


def fetch_one(date_str: str) -> pd.DataFrame:
    """拉单日 CME 数据；网络失败向上抛异常，空结果返回空 DataFrame。"""
    import akshare as ak

    return ak.crypto_bitcoin_cme(date=date_str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"拉取工作日数量（默认 {DEFAULT_DAYS}）")
    parser.add_argument("--end", default=None, help="截止日 YYYY-MM-DD（默认北京时间今天）")
    parser.add_argument("--out", default=None, help="覆盖输出路径（默认写死宏数据目录）")
    args = parser.parse_args()

    end = pd.Timestamp(args.end) if args.end else beijing_today()
    out_path = Path(args.out) if args.out else OUT_PATH
    bdays = pd.bdate_range(end=end, periods=args.days)

    rows: list[pd.DataFrame] = []
    failed: list[str] = []      # 网络/接口异常
    empty_days: list[str] = []  # 正常返回但无数据（周末/节假日/上游未发布）
    pulled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for i, d in enumerate(bdays, 1):
        ds = d.strftime("%Y%m%d")
        try:
            df = fetch_one(ds)
        except Exception as exc:  # noqa: BLE001 — 单日失败不应中断整窗快照
            failed.append(f"{ds}({type(exc).__name__}:{str(exc)[:60]})")
            continue
        if df is None or df.empty:
            empty_days.append(ds)
            continue
        df = df.copy()
        for c in NUMERIC_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df.insert(0, "date", d.normalize())
        df["source"] = SOURCE
        df["pulled_at"] = pulled_at
        rows.append(df)
        if i % 10 == 0 or i == len(bdays):
            print(f"  [125] {i}/{len(bdays)} 天，累计成功 {len(rows)} 天")

    if not rows:
        print("[125] FAIL: 45 个工作日全部失败/空，未写出 parquet")
        print(f"[125] 失败: {failed}")
        print(f"[125] 空: {empty_days}")
        sys.exit(1)

    new_df = pd.concat(rows, ignore_index=True)

    # 幂等合并：已存在 parquet 时去重追加（重跑不重复）
    old_df = pd.read_parquet(out_path) if out_path.exists() else None
    if old_df is not None:
        merged = pd.concat([old_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["date", "商品", "类型"], keep="last")
    else:
        merged = new_df
    merged = merged.sort_values(["date", "商品", "类型"]).reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)

    # ---- 摘要输出 ----
    print(f"\n[125] CME 快照完成")
    print(f"  工作日窗口: {bdays[0]:%Y-%m-%d} → {bdays[-1]:%Y-%m-%d}（{len(bdays)} 个工作日，end={end:%Y-%m-%d} 北京时间）")
    print(f"  成功: {len(rows)} 天 | 空结果: {len(empty_days)} 天 | 失败: {len(failed)} 天")
    if failed:
        print(f"  失败明细: {failed}")
    if empty_days:
        print(f"  空结果明细（周末/节假日/上游未发布）: {empty_days}")
    print(f"  本次新增行: {len(new_df)} | 合并后总行数: {len(merged)}")
    print(f"  实际数据覆盖: {merged['date'].min():%Y-%m-%d} → {merged['date'].max():%Y-%m-%d}"
          f"（最近数据滞后 {max(0, (end - merged['date'].max()).days)} 天）")
    print(f"  pulled_at(UTC): {pulled_at}")
    print(f"  输出: {out_path}")

    # 摘要表：每交易日 比特币期货 OI / 持仓变化 / 微型比特币期货 OI
    piv = merged[merged["类型"] == "期货"].pivot_table(
        index="date", columns="商品", values="未平仓合约", aggfunc="first",
    ).rename(columns={"比特币": "BTC期货OI", "微型比特币": "MBTC期货OI"})
    chg = merged[(merged["商品"] == "比特币") & (merged["类型"] == "期货")].set_index("date")["持仓变化"]
    summ = piv.join(chg.rename("BTC持仓变化")).sort_index()
    print("\n[125] 摘要表（最近 12 个交易日，比特币期货 OI 单位=张）")
    print(summ.tail(12).to_string())


if __name__ == "__main__":
    main()
