"""
DeepResearchPromptPackage v1 — 候选因子解释 + 质量闸 + 结构化提示词数据包。

纯函数，无文件写入，无网络请求，无全局状态。
供主线后端以后接入，当前阶段仅做隔离单元测试。

P0/P1 返工（2026-07-11 第二轮）：
  - P0: 有效 cutoff 严格语义（scan_ms 必须可解析，cutoff = min(scan, manifest)）
  - P0: manifest cutoff > scan → BLOCK，但有效 cutoff 仍取 scan_ms
  - P0: cutoff == scan → 合法，不 BLOCK
  - P0: 无 manifest cutoff → 有效 cutoff = scan_ms
  - P0: 所有 snapshot 行必须 <= effective_cutoff_ms，越界则 BLOCK
  - P1: 稳定的 candidate_metrics
  - P1: 固定 trigger UI 契约（explanation_zh / limitation_zh）

ANTI-P0-001 返工（2026-07-12）：
  - P0-1: run_info 必须从真实 manifest 读取，缺失 fail closed
  - P0-2: 拆分质量闸为 integrity/identity/history/derivatives/liquidity/paper_eligibility gate
  - P0-3: 统一 paper_eligibility 输出结构
  - P0-4: 区分 last_bar_turnover_usd / turnover_24h_usd / turnover_valid_bars_24h
  - P0-5: 研究输出枚举改为方向中立枚举
  - P0-7: human_checks 统一为对象
  - P0-9: 分离 content_hash / artifact_hash / input_fingerprint
  - P0-10: run_id / 文件路径安全校验
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 版本常量
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "deep_research_prompt_package_v1"
TEMPLATE_VERSION = "v1"
GENERATOR_VERSION = "deep_research_package.v1"

VALID_MODES = {"HISTORICAL_REPLAY", "PROSPECTIVE_LIVE"}

GATE_NOT_IMPLEMENTED_WARNING = "GATE_NOT_IMPLEMENTED: 未执行真实流动性/身份检查"

# P0-5: 方向中立研究输出枚举（禁止 LONG_THESIS_STRONGER / SHORT_THESIS_STRONGER）
VALID_RESEARCH_VERDICTS = {
    "CONTINUATION_EVIDENCE_STRONGER",
    "REVERSAL_EVIDENCE_STRONGER",
    "MEAN_REVERSION_EVIDENCE_STRONGER",
    "DATA_ARTIFACT_LIKELY",
    "MIXED",
    "NO_TRADE_BLOCKER",
    "INSUFFICIENT_EVIDENCE",
}

PROHIBITED_RESEARCH_VERDICTS = {
    "LONG_THESIS_STRONGER",
    "SHORT_THESIS_STRONGER",
}

# P0-10: 安全路径/ID 正则
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
_SAFE_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def validate_safe_id(value: str, label: str = "id") -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def validate_safe_path(path_str: str, label: str = "path") -> str:
    segments = path_str.replace("\\", "/").split("/")
    for seg in segments:
        if seg in (".", "..") or not _SAFE_PATH_SEGMENT_RE.match(seg):
            raise ValueError(f"path traversal or unsafe {label}: {path_str!r}")
    return path_str


def validate_run_info(run_info: dict) -> dict:
    """P0-1: run_info 必须包含 status / eligible_for_judgment / hashes，缺失 fail closed。"""
    required = {"status", "eligible_for_judgment", "hashes"}
    missing = required - set(run_info.keys())
    if missing:
        raise ValueError(f"run_info missing required fields: {sorted(missing)}")
    if run_info["status"] is None:
        raise ValueError("run_info.status must not be None (fail closed)")
    if run_info["eligible_for_judgment"] is None:
        raise ValueError("run_info.eligible_for_judgment must not be None (fail closed)")
    return run_info

# ---------------------------------------------------------------------------
# Trigger catalog
# ---------------------------------------------------------------------------
TRIGGER_CATALOG: dict[str, dict[str, Any]] = {
    "vol_quantile_high": {
        "label_zh": "24小时波动处于自身90天高分位",
        "description": "当前24小时实现波动位于该标的自身过去90天的高分位，说明波动状态异常。",
        "explanation_zh": "当前24小时实现波动位于该标的自身过去90天的高分位，说明波动状态异常。",
        "limitation_zh": "不表示多空方向，也不证明异常会延续或反转。",
        "implementation_status": "COMPUTED",
        "observation_key": "trigger_quantile",
        "threshold": 0.90,
        "unit": "分位",
    },
    "vol_quantile_low": {
        "label_zh": "异常低波动",
        "description": "配置已预留，但当前扫描器尚未实现。",
        "explanation_zh": "配置已预留，但当前扫描器尚未实现。",
        "limitation_zh": "不得展示为已触发或用0代替缺失值。",
        "implementation_status": "NOT_COMPUTED",
        "observation_key": "trigger_quantile",
        "threshold": 0.10,
        "unit": "分位",
    },
    "large_move_abs": {
        "label_zh": "24小时绝对涨跌超过阈值",
        "description": "标的24小时绝对涨跌幅超过扫描阈值，值得核验事件、流动性和数据真实性。",
        "explanation_zh": "标的24小时绝对涨跌幅超过扫描阈值，值得核验事件、流动性和数据真实性。",
        "limitation_zh": "可能包含整体市场Beta、项目事件或数据异常，不直接产生方向结论。",
        "implementation_status": "COMPUTED",
        "observation_key": "abs_move_pct_24h",
        "threshold": 10.0,
        "unit": "%",
    },
    "large_move_excess": {
        "label_zh": "24小时相对BTC超额涨跌超过阈值",
        "description": "扣除BTC同期涨跌后仍存在显著异动，说明仅用BTC一阶市场Beta无法解释。",
        "explanation_zh": "扣除BTC同期涨跌后仍存在显著异动，说明仅用BTC一阶市场Beta无法解释。",
        "limitation_zh": "尚未剔除板块Beta、事件冲击和多重检验影响，不等于可交易Alpha。",
        "implementation_status": "COMPUTED",
        "observation_key": "excess_move_pct_24h",
        "threshold": 7.0,
        "unit": "%",
    },
    "oi_change_quantile_high": {
        "label_zh": "OI变化处于高分位",
        "description": "配置已预留，但当前扫描器尚未计算24小时OI变化分位。",
        "explanation_zh": "配置已预留，但当前扫描器尚未计算24小时OI变化分位。",
        "limitation_zh": "不得推测OI拥挤或方向。",
        "implementation_status": "NOT_COMPUTED",
        "observation_key": "oi_change_pct_24h",
        "threshold": 0.90,
        "unit": "分位",
    },
    "funding_quantile_high": {
        "label_zh": "资金费率处于高分位",
        "description": "配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。",
        "explanation_zh": "配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。",
        "limitation_zh": "funding符号只用于成本和拥挤背景，不能单独给方向。",
        "implementation_status": "NOT_COMPUTED",
        "observation_key": "funding_rate_8h",
        "threshold": 0.90,
        "unit": "分位",
    },
    "funding_quantile_low": {
        "label_zh": "资金费率处于低分位",
        "description": "配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。",
        "explanation_zh": "配置已预留，但当前扫描器只记录最新资金费率，尚未计算分位。",
        "limitation_zh": "funding符号只用于成本和拥挤背景，不能单独给方向。",
        "implementation_status": "NOT_COMPUTED",
        "observation_key": "funding_rate_8h",
        "threshold": 0.10,
        "unit": "分位",
    },
}

# ---------------------------------------------------------------------------
# 字段 allowlist + denylist
# ---------------------------------------------------------------------------
DENYLIST_FIELDS: set[str] = {
    "exit_price_ref_4h", "exit_price_ref_24h", "exit_price_ref_72h", "exit_price_ref_7d",
    "btc_exit_price_4h", "btc_exit_price_24h", "btc_exit_price_72h", "btc_exit_price_7d",
    "btc_entry_price",
    "dir_excess_ret_4h", "dir_excess_ret_24h", "dir_excess_ret_72h", "dir_excess_ret_7d",
    "dir_excess_ret_net_4h", "dir_excess_ret_net_24h",
    "dir_excess_ret_net_72h", "dir_excess_ret_net_7d",
    "friction_bps_roundtrip", "funding_cost_component",
    "return_tape", "evaluation", "falsified",
    "testable_hypothesis", "decision_time_utc", "notes",
    "hypotheses_validated", "post_decision_notes",
}

ALLOWED_CANDIDATE_FIELDS: set[str] = {
    "schema_version", "run_id", "record_id", "scan_time_utc",
    "symbol", "rank", "turnover_24h_usd",
    "history_tier", "eligible_for_paper",
    "trigger_reason", "trigger_metric", "trigger_value", "trigger_quantile",
    "large_move_flag_24h", "abs_move_pct_24h", "excess_move_pct_24h",
    "funding_sign", "funding_rate_8h", "oi_change_pct_24h",
    "is_top_candidate", "decision", "direction", "direction_sign",
}

ALLOWED_RUN_FIELDS: set[str] = {
    "run_id", "status", "reason", "created_utc",
    "eligible_for_dod", "eligible_for_judgment",
    "superseded_by", "hashes",
}

ALLOWED_MANIFEST_FIELDS: set[str] = {
    "schema_version", "run_id", "scan_time_utc", "data_cutoff",
    "snapshot_sha256", "symbol_meta_sha256",
    "return_tape_sha256", "benchmark_symbol",
    "benchmark_frozen_in_snapshot", "candidate_count", "integrity",
    "snapshot_path", "symbol_meta_path",
    "return_tape_path",
}

ALLOWED_MARKET_SNAPSHOT_FIELDS: set[str] = {
    "timestamp_utc", "open", "high", "low", "close", "volume", "turnover_usd",
    "funding_rate_8h", "open_interest",
    "last_close", "last_open", "last_high", "last_low",
    "last_volume", "last_turnover_usd", "ret_24h_pct",
    "last_complete_bar_timestamp_utc",
}

ALLOWED_CANDIDATE_METRICS_FIELDS: set[str] = {
    "symbol_return_24h_pct",
    "btc_return_24h_pct",
    "excess_return_24h_pct",
    "realized_vol_24h_decimal",
    "realized_vol_quantile",
    "last_bar_turnover_usd",
    "turnover_24h_usd",
    "turnover_valid_bars_24h",
    "funding_rate_8h_decimal",
    "funding_rate_8h_percent",
    "funding_sign",
    "oi_current",
    "oi_change_24h_pct",
    "last_complete_bar_timestamp_utc",
}

# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
@dataclass
class HumanCheckItem:
    """P0-7: human_checks 统一为对象。"""
    code: str
    item: str
    reason: str
    blocking: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SubGateResult:
    """P0-2: 单个子质量闸结果。"""
    gate: str
    status: str  # PASS / WARN / BLOCK
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QualityGateResult:
    status: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    required_human_checks: list[dict] = field(default_factory=list)
    sub_gates: list[dict] = field(default_factory=list)
    paper_eligibility: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TriggerItem:
    code: str
    label_zh: str
    description: str = ""
    explanation_zh: str = ""
    limitation_zh: str = ""
    implementation_status: str = ""        # COMPUTED | NOT_COMPUTED
    triggered: bool = False                 # 本候选是否触发
    observation: Optional[float] = None
    threshold: Optional[float] = None
    unit: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarketSnapshotRow:
    timestamp_utc: Optional[int]
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    turnover_usd: Optional[float]
    funding_rate_8h: Optional[float]
    open_interest: Optional[float]

    @classmethod
    def from_dict(cls, d: dict) -> "MarketSnapshotRow":
        return cls(
            timestamp_utc=d.get("timestamp_utc"),
            open=d.get("open"),
            high=d.get("high"),
            low=d.get("low"),
            close=d.get("close"),
            volume=d.get("volume"),
            turnover_usd=d.get("turnover_usd"),
            funding_rate_8h=d.get("funding_rate_8h"),
            open_interest=d.get("open_interest"),
        )

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ---------------------------------------------------------------------------
# 时间标准化
# ---------------------------------------------------------------------------

def _parse_ts_to_ms(raw: Any) -> Optional[int]:
    """统一时间解析：支持 Unix 秒/毫秒、ISO 字符串、timestamp_utc、timestamp。
    返回 Unix 毫秒，解析失败返回 None（fail closed）。"""
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        if raw >= 1e15:
            return int(raw / 1e6)
        if raw >= 1e12:
            return int(raw)
        return int(raw * 1000)

    if isinstance(raw, str):
        raw_s = raw.strip()
        if not raw_s:
            return None
        if "T" in raw_s or raw_s.endswith("Z"):
            try:
                dt = datetime.fromisoformat(raw_s.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                return None
        if raw_s.replace(".", "").replace("-", "").replace("e", "").replace("E", "").isdigit():
            try:
                return _parse_ts_to_ms(float(raw_s))
            except ValueError:
                return None

    return None


def _normalize_snapshot_row(row: dict) -> dict:
    """为快照行增加标准化 timestamp_utc 字段。
    优先用已有 timestamp_utc，其次用 timestamp。
    两者同时存在但冲突时报 ValueError（fail closed）。"""
    result = dict(row)
    ts_raw_utc = row.get("timestamp_utc")
    ts_raw_ts = row.get("timestamp")

    ms_utc = _parse_ts_to_ms(ts_raw_utc) if ts_raw_utc is not None else None
    ms_ts = _parse_ts_to_ms(ts_raw_ts) if ts_raw_ts is not None else None

    if ms_utc is not None and ms_ts is not None:
        if ms_utc != ms_ts:
            raise ValueError(
                f"timestamp_utc={ts_raw_utc} and timestamp={ts_raw_ts} conflict "
                f"({ms_utc}ms != {ms_ts}ms)"
            )
        result["timestamp_utc"] = ms_utc
    elif ms_utc is not None:
        result["timestamp_utc"] = ms_utc
    elif ms_ts is not None:
        result["timestamp_utc"] = ms_ts
    else:
        result["timestamp_utc"] = None

    return result


def _resolve_effective_cutoff(
    scan_time_utc: str,
    manifest_data_cutoff: Optional[int],
) -> tuple[int, list[str]]:
    """解析有效 cutoff，返回 (effective_cutoff_ms, blockers)。

    规则：
    - scan_time_utc 必须可解析，否则 fail closed。
    - manifest cutoff 不存在 → effective = scan_ms。
    - manifest cutoff == scan_ms → 合法，不阻断。
    - manifest cutoff > scan_ms → BLOCK（未来数据嫌疑），但 effective 仍取 scan_ms。
    - manifest cutoff < scan_ms → effective = manifest cutoff。
    """
    blockers: list[str] = []
    scan_ms = _parse_ts_to_ms(scan_time_utc)
    if scan_ms is None:
        raise ValueError(f"scan_time_utc unparseable: {scan_time_utc!r}")

    if manifest_data_cutoff is None:
        return scan_ms, blockers

    manifest_cutoff_ms = int(manifest_data_cutoff)
    if manifest_cutoff_ms > scan_ms:
        blockers.append(
            f"manifest_cutoff_after_scan: manifest={manifest_cutoff_ms} > scan={scan_ms}"
        )
        return scan_ms, blockers
    elif manifest_cutoff_ms == scan_ms:
        return manifest_cutoff_ms, blockers
    else:
        return manifest_cutoff_ms, blockers


def _enforce_cutoff(
    rows: list[dict],
    effective_cutoff_ms: int,
) -> tuple[list[dict], list[str]]:
    """防御性 cutoff 校验：仅保留 timestamp_utc <= effective_cutoff_ms 的行。

    返回 (合法行列表, integrity blockers)。
    任何 cutoff 后数据不得进入 package 或 rendered prompt。
    """
    blockers: list[str] = []
    if not rows:
        return [], blockers

    clean_rows: list[dict] = []
    post_cutoff_count = 0

    for row in rows:
        ts_ms = row.get("timestamp_utc")
        if ts_ms is None:
            blockers.append(f"row timestamp_unparseable: {row.get('symbol', '?')}")
            continue

        if ts_ms > effective_cutoff_ms:
            post_cutoff_count += 1
            continue

        clean_rows.append(row)

    if post_cutoff_count > 0:
        blockers.append(
            f"post_cutoff_rows_filtered={post_cutoff_count}; "
            f"effective_cutoff_ms={effective_cutoff_ms}"
        )

    return clean_rows, blockers


# ---------------------------------------------------------------------------
# 核心工具函数
# ---------------------------------------------------------------------------

def _compute_package_hash(package_dict: dict) -> str:
    canonical = json.dumps(package_dict, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _short_hash(seed: str, length: int = 12) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:length]


def _make_package_id(run_id: str, record_id: str, generated_at_utc: str) -> str:
    seed = f"{run_id}|{record_id}|{generated_at_utc}"
    return f"drp_{_short_hash(seed)}"


def _is_missing(val: Any) -> bool:
    """P1: 修正缺失判断。只有 None / 空字符串 / NaN 才算缺失。
    合法的 0 不视为缺失。"""
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    if isinstance(val, float) and str(val) == "nan":
        return True
    return False


def _safe_float(val: Any) -> Optional[float]:
    """安全转换为 float；None / 空字符串 / NaN → None；合法 0 → 0.0。"""
    if _is_missing(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _sanitize_candidate(candidate: dict) -> dict:
    allowed = ALLOWED_CANDIDATE_FIELDS - DENYLIST_FIELDS
    return {k: v for k, v in candidate.items() if k in allowed}


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def build_signal_explanations(
    candidate: dict,
    scan_rules: dict,
) -> list[dict]:
    """构建候选因子解释列表。"""
    trigger_codes: set[str] = {
        t.strip() for t in str(candidate.get("trigger_reason", "")).split("|") if t.strip()
    }

    results: list[dict] = []
    for code, cfg in TRIGGER_CATALOG.items():
        triggered = code in trigger_codes

        thr = None
        obs: Optional[float] = None

        rule_map = {
            "vol_quantile_high": ("triggers", "vol_quantile_high"),
            "vol_quantile_low": ("triggers", "vol_quantile_low"),
            "oi_change_quantile_high": ("triggers", "oi_change_quantile_high"),
            "funding_quantile_high": ("triggers", "funding_quantile_high"),
            "funding_quantile_low": ("triggers", "funding_quantile_low"),
            "large_move_abs": ("large_move", "large_move_threshold_abs_pct_24h"),
            "large_move_excess": ("large_move", "large_move_threshold_excess_pct_24h"),
        }
        if code in rule_map:
            section, key = rule_map[code]
            thr = float(scan_rules.get(section, {}).get(key, cfg.get("threshold", 0)))

        obs_key = cfg.get("observation_key")
        if triggered and obs_key:
            obs = _safe_float(candidate.get(obs_key))

        results.append(TriggerItem(
            code=code,
            label_zh=cfg["label_zh"],
            description=cfg["description"],
            explanation_zh=cfg["explanation_zh"],
            limitation_zh=cfg["limitation_zh"],
            implementation_status=cfg["implementation_status"],
            triggered=triggered,
            observation=obs,
            threshold=thr,
            unit=cfg["unit"],
        ).to_dict())

    return results





def _run_missing_fields(
    candidate: dict,
) -> list[str]:
    """P1: 仅根据当前 trigger 判断缺失，合法 0 不判 missing。"""
    trigger_codes: set[str] = {
        t.strip() for t in str(candidate.get("trigger_reason", "")).split("|") if t.strip()
    }

    trigger_field_map: dict[str, list[str]] = {
        "vol_quantile_high": ["trigger_quantile"],
        "vol_quantile_low": ["trigger_quantile"],
        "large_move_abs": ["abs_move_pct_24h"],
        "large_move_excess": ["excess_move_pct_24h"],
        "oi_change_quantile_high": ["oi_change_pct_24h"],
        "funding_quantile_high": ["funding_rate_8h"],
        "funding_quantile_low": ["funding_rate_8h"],
    }

    general_fields = ["funding_rate_8h"]
    required: set[str] = set(general_fields)
    for code in trigger_codes:
        required.update(trigger_field_map.get(code, []))

    return [f for f in sorted(required) if _safe_float(candidate.get(f)) is None]


def _funding_display(funding_decimal: Optional[float]) -> dict:
    result: dict[str, Any] = {
        "funding_rate_8h_decimal": funding_decimal,
        "funding_rate_8h_percent": None,
        "source_unit": "decimal",
        "validation_status": "unknown",
    }
    if funding_decimal is None:
        result["validation_status"] = "not_provided"
        return result

    result["funding_rate_8h_percent"] = round(funding_decimal * 100, 8)
    med = abs(funding_decimal)
    from harness.lib.funding_normalize import normalized_funding_abs_max

    if med > normalized_funding_abs_max():
        result["validation_status"] = "above_abs_max — 可能单位错误"
    else:
        result["validation_status"] = "within_normal_range"
    return result


def _market_snapshot_from_safe_rows(
    rows: list[dict],
    symbol: Optional[str] = None,
) -> dict:
    """从防御性 cutoff 过滤后的安全快照行中提取市场快照。"""
    if not rows:
        return {"timestamp_utc": None, "last_close": None}

    filtered = [r for r in rows if r.get("symbol") == symbol] if symbol else rows
    sorted_rows = sorted(filtered, key=lambda r: r.get("timestamp_utc", 0) or 0)
    if not sorted_rows:
        return {"timestamp_utc": None, "last_close": None}

    latest = sorted_rows[-1]
    if len(sorted_rows) >= 25:
        prev = sorted_rows[-25]
    else:
        prev = sorted_rows[0]

    close_latest = _safe_float(latest.get("close"))
    close_prev = _safe_float(prev.get("close"))
    ret_24h = (close_latest / close_prev - 1.0) * 100 if (close_latest is not None and close_prev is not None and close_prev != 0) else None

    last_bar_ts = latest.get("timestamp_utc")

    return {
        "timestamp_utc": last_bar_ts,
        "last_complete_bar_timestamp_utc": last_bar_ts,
        "last_close": close_latest,
        "last_open": _safe_float(latest.get("open")),
        "last_high": _safe_float(latest.get("high")),
        "last_low": _safe_float(latest.get("low")),
        "last_volume": _safe_float(latest.get("volume")),
        "last_turnover_usd": _safe_float(latest.get("turnover_usd")),
        "funding_rate_8h": _safe_float(latest.get("funding_rate_8h")),
        "open_interest": _safe_float(latest.get("open_interest")),
        "ret_24h_pct": round(ret_24h, 6) if ret_24h is not None else None,
    }


def _build_candidate_metrics(candidate: dict, target_snap: dict, btc_snap: dict) -> dict:
    """构建稳定的 candidate_metrics，字段来源明确，缺失保持 null。"""
    abs_move = _safe_float(candidate.get("abs_move_pct_24h"))
    excess = _safe_float(candidate.get("excess_move_pct_24h"))
    # BTC return = symbol - excess，四舍五入到 6 位小数避免浮点精度伪匹配
    btc_ret = round(abs_move - excess, 6) if (abs_move is not None and excess is not None) else None

    funding_raw = _safe_float(candidate.get("funding_rate_8h"))
    funding_display = _funding_display(funding_raw)

    return {
        "symbol_return_24h_pct": abs_move,
        "btc_return_24h_pct": btc_ret,
        "excess_return_24h_pct": excess,
        "realized_vol_24h_decimal": _safe_float(candidate.get("trigger_value")) if candidate.get("trigger_metric") == "vol_24h" else None,
        "realized_vol_quantile": _safe_float(candidate.get("trigger_quantile")),
        "last_bar_turnover_usd": _safe_float(target_snap.get("last_turnover_usd")),
        "turnover_24h_usd": _safe_float(candidate.get("turnover_24h_usd")),
        "turnover_valid_bars_24h": _safe_float(candidate.get("turnover_valid_bars_24h")),
        "funding_rate_8h_decimal": funding_raw,
        "funding_rate_8h_percent": funding_display.get("funding_rate_8h_percent"),
        "funding_sign": candidate.get("funding_sign"),
        "oi_current": _safe_float(target_snap.get("open_interest")),
        "oi_change_24h_pct": _safe_float(candidate.get("oi_change_pct_24h")),
        "last_complete_bar_timestamp_utc": target_snap.get("last_complete_bar_timestamp_utc"),
    }


def _boolish(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return None


def _first_numeric(*values: Any) -> Optional[float]:
    for value in values:
        parsed = _safe_float(value)
        if parsed is not None:
            return parsed
    return None


def _evaluate_identity_gate(
    candidate: dict,
    symbol_meta: dict,
    known_symbols: Optional[list[str]] = None,
) -> dict:
    """Bounded identity check; migration history remains explicitly unavailable."""
    blockers: list[str] = []
    warnings: list[str] = []
    human_checks: list[dict] = []
    raw_candidate_symbol = str(candidate.get("symbol") or "").strip()
    symbol = raw_candidate_symbol.upper()
    if not symbol:
        blockers.append("missing_symbol")
    elif not re.fullmatch(r"[A-Z0-9]+USDT", symbol):
        blockers.append("unparseable_symbol")

    if not symbol_meta:
        blockers.append("missing_symbol_meta")

    candidate_identity = str(candidate.get("contract_identity") or "").strip()
    meta_identity = str(symbol_meta.get("contract_identity") or "").strip()
    if not candidate_identity and not meta_identity:
        blockers.append("missing_contract_identity")
    if candidate_identity and meta_identity and candidate_identity != meta_identity:
        blockers.append("contract_identity_mismatch")

    if known_symbols:
        normalized_known = {str(item).strip().upper() for item in known_symbols if str(item).strip()}
        if symbol and symbol not in normalized_known:
            blockers.append("symbol_not_in_known_list")
    else:
        warnings.append("KNOWN_LIST_NOT_AVAILABLE")
        human_checks.append(HumanCheckItem(
            code="IDENTITY_KNOWN_LIST_NOT_AVAILABLE",
            item="identity_gate",
            reason="本次 package 未携带 universe known-list，无法完成清单核对",
            blocking=False,
        ).to_dict())

    migration_status = "NOT_AVAILABLE"
    warnings.append("migration_history_status=NOT_AVAILABLE")
    human_checks.append(HumanCheckItem(
        code="IDENTITY_MIGRATION_HISTORY_NOT_AVAILABLE",
        item="identity_gate",
        reason="当前数据源没有合约迁移/重命名历史，需人工或外部数据核对",
        blocking=False,
    ).to_dict())
    return {
        "status": "BLOCK" if blockers else "WARN",
        "blockers": blockers,
        "warnings": warnings,
        "human_checks": human_checks,
        "migration_history_status": migration_status,
        "known_list_status": "PASS" if known_symbols else "NOT_AVAILABLE",
    }


def _evaluate_liquidity_gate(
    candidate: dict,
    symbol_meta: dict,
    scan_rules: dict,
    manifest: Optional[dict] = None,
) -> dict:
    """Bounded turnover/bar check with explicit spread/depth gaps."""
    blockers: list[str] = []
    warnings: list[str] = []
    human_checks: list[dict] = []
    baseline = scan_rules.get("baseline_pool", {}) or {}
    min_turnover = _safe_float(baseline.get("min_effective_turnover_usd"))
    min_valid_bars = _safe_float(baseline.get("min_valid_turnover_bars_24h"))
    turnover = _first_numeric(candidate.get("turnover_24h_usd"), symbol_meta.get("turnover_24h_usd_effective"))
    valid_bars = _first_numeric(candidate.get("turnover_valid_bars_24h"), symbol_meta.get("n_valid_bars"))
    config_available = min_turnover is not None and min_valid_bars is not None
    if not config_available:
        warnings.append("LIQUIDITY_CONFIG_NOT_PROVIDED_TO_PURE_GATE")
    if turnover is None:
        (blockers if config_available else warnings).append("missing_turnover")
    elif config_available and turnover < min_turnover:
        blockers.append("turnover_below_minimum")
    if valid_bars is None:
        (blockers if config_available else warnings).append("missing_valid_turnover_bars")
    elif config_available and valid_bars < min_valid_bars:
        blockers.append("valid_turnover_bars_below_minimum")

    explicit_threshold_pass = _boolish(symbol_meta.get("threshold_pass"))
    explicit_valid_pass = _boolish(symbol_meta.get("valid_bar_pass"))
    if explicit_threshold_pass is False:
        blockers.append("turnover_threshold_status_failed")
    if explicit_valid_pass is False:
        blockers.append("valid_bar_status_failed")

    integrity = (manifest or {}).get("integrity", {}) or {}
    if integrity.get("no_lookahead_attested") is False or integrity.get("completed_bar_violations", 0):
        blockers.append("time_integrity_failed")
    elif manifest and (manifest.get("bar_resolution") is None or manifest.get("resolved_effective_cutoff_ms") is None):
        warnings.append("TIME_INTEGRITY_EVIDENCE_MISSING")

    warnings.extend(["spread_status=NOT_AVAILABLE", "depth_status=NOT_AVAILABLE"])
    human_checks.extend([
        HumanCheckItem(
            code="LIQUIDITY_SPREAD_NOT_AVAILABLE",
            item="liquidity_gate",
            reason="当前没有真实 bid-ask spread 数据，不使用估计 bps",
            blocking=False,
        ).to_dict(),
        HumanCheckItem(
            code="LIQUIDITY_DEPTH_NOT_AVAILABLE",
            item="liquidity_gate",
            reason="当前没有真实 order-book depth 数据，不使用估计深度",
            blocking=False,
        ).to_dict(),
    ])
    return {
        "status": "BLOCK" if blockers else "WARN",
        "blockers": blockers,
        "warnings": warnings,
        "human_checks": human_checks,
        "turnover_24h_usd": turnover,
        "valid_turnover_bars_24h": valid_bars,
        "spread_status": "NOT_AVAILABLE",
        "depth_status": "NOT_AVAILABLE",
    }


def _resolve_paper_eligibility(
    candidate: dict,
    identity_gate: dict,
    liquidity_gate: dict,
    derivatives_warnings: list[str],
    history_warnings: list[str],
    integrity_blockers: list[str],
) -> dict:
    """Resolve paper status with ALLOW deliberately parked for this release."""
    ep = str(candidate.get("eligible_for_paper", "")).strip().lower()
    blockers = list(integrity_blockers) + list(identity_gate.get("blockers", [])) + list(liquidity_gate.get("blockers", []))
    reason_codes: list[str] = []
    warnings: list[str] = []
    if ep == "yes" and not blockers:
        reason_codes.append("PAPER_ALLOW_POLICY_PARKED")
        if identity_gate.get("warnings"):
            reason_codes.append("IDENTITY_WARN")
        if liquidity_gate.get("warnings"):
            reason_codes.append("LIQUIDITY_WARN")
        if derivatives_warnings:
            reason_codes.append("DERIVATIVES_WARN")
        if history_warnings:
            reason_codes.append("HISTORY_WARN")
        warnings.append("paper ALLOW policy is PARKED; status forced REVIEW_REQUIRED")
        return {
            "status": "REVIEW_REQUIRED",
            "gate_status": "WARN",
            "blockers": [],
            "warnings": warnings,
            "reason_codes": reason_codes,
            "owner_override_allowed": False,
        }

    if ep == "partial" or str(candidate.get("history_tier", "")).strip().lower() == "partial":
        if "PARTIAL_HISTORY" not in reason_codes:
            reason_codes.append("PARTIAL_HISTORY")
        if not blockers:
            warnings.append("partial history requires review")

    if blockers:
        if integrity_blockers:
            reason_codes.append("INTEGRITY_BLOCK")
        if identity_gate.get("blockers"):
            reason_codes.append("IDENTITY_BLOCK")
        if liquidity_gate.get("blockers"):
            reason_codes.append("LIQUIDITY_BLOCK")
        return {
            "status": "BLOCK",
            "gate_status": "BLOCK",
            "blockers": (
                ["paper_blocked_by_integrity"]
                if integrity_blockers and not identity_gate.get("blockers") and not liquidity_gate.get("blockers")
                else list(identity_gate.get("blockers", [])) + list(liquidity_gate.get("blockers", []))
            ),
            "warnings": warnings,
            "reason_codes": reason_codes,
            "owner_override_allowed": False,
        }

    if ep == "partial" or str(candidate.get("history_tier", "")).strip().lower() == "partial":
        return {
            "status": "REVIEW_REQUIRED",
            "gate_status": "WARN",
            "blockers": [],
            "warnings": warnings,
            "reason_codes": reason_codes,
            "owner_override_allowed": False,
        }
    return {
        "status": "BLOCK",
        "gate_status": "BLOCK",
        "blockers": [f"eligible_for_paper={candidate.get('eligible_for_paper', 'NOT_PROVIDED')}"],
        "warnings": warnings,
        "reason_codes": ["NOT_ELIGIBLE"],
        "owner_override_allowed": False,
    }


def evaluate_quality_gate(
    candidate: dict,
    run_info: dict,
    manifest: dict,
    symbol_meta: dict,
    scan_rules: dict,
    mode: Optional[str],
    cutoff_blockers: Optional[list[str]] = None,
) -> dict:
    """评估候选质量闸并拆分子闸。"""
    sub_gates = []
    blockers = []
    warnings = []
    human_checks: list[dict] = []
    
    # 1. integrity_gate
    ig_blockers = []
    run_status = str(run_info.get("status", "")).lower()
    if run_status != "clean":
        ig_blockers.append(f"run_status={run_info.get('status', 'MISSING')}")
    if not run_info.get("eligible_for_judgment", False):
        ig_blockers.append("eligible_for_judgment=false")
    run_hashes = run_info.get("hashes", {}) or {}
    for key in ("snapshot_sha256", "symbol_meta_sha256", "return_tape_sha256"):
        run_hash = run_hashes.get(f"input_{key}" if key == "snapshot_sha256" else key)
        manifest_hash = manifest.get(key)
        if run_hash and manifest_hash and run_hash != manifest_hash:
            ig_blockers.append(f"{key}_hash_mismatch")
    if mode is not None and mode not in VALID_MODES:
        ig_blockers.append(f"invalid_mode={mode}")
    if cutoff_blockers:
        ig_blockers.extend(cutoff_blockers)
    sub_gates.append(SubGateResult(gate="integrity_gate", status="BLOCK" if ig_blockers else "PASS", blockers=ig_blockers).to_dict())
    blockers.extend(ig_blockers)

    # 2. identity_gate
    identity_gate = _evaluate_identity_gate(
        candidate,
        symbol_meta,
        known_symbols=manifest.get("known_symbols"),
    )
    human_checks.extend(identity_gate["human_checks"])
    sub_gates.append(SubGateResult(
        gate="identity_gate",
        status=identity_gate["status"],
        blockers=identity_gate["blockers"],
        warnings=identity_gate["warnings"],
    ).to_dict())
    blockers.extend(identity_gate["blockers"])
    warnings.extend(identity_gate["warnings"])

    # 3. history_gate
    hg_warnings = []
    ht = str(candidate.get("history_tier", "")).strip().lower()
    if ht == "partial":
        hg_warnings.append("history_tier=Partial")
        human_checks.append(HumanCheckItem(
            code="PARTIAL_HISTORY",
            item="history_tier",
            reason="基线对照不足，人工确认后进入 Paper 计划",
            blocking=False
        ).to_dict())
    sub_gates.append(SubGateResult(gate="history_gate", status="WARN" if hg_warnings else "PASS", warnings=hg_warnings).to_dict())
    warnings.extend(hg_warnings)

    # 4. derivatives_gate
    dg_warnings = []
    if _safe_float(candidate.get("funding_rate_8h")) is None:
        dg_warnings.append("missing_funding_rate")
    if candidate.get("open_interest") in (None, ""):
        dg_warnings.append("missing_open_interest")
    for prefix in ("oi", "funding"):
        metric_status = str(symbol_meta.get(f"{prefix}_status", "")).strip().upper()
        if metric_status in {"PARTIAL", "NOT_COMPUTED"}:
            dg_warnings.append(f"{prefix}_status={metric_status}")
    sub_gates.append(SubGateResult(gate="derivatives_gate", status="WARN" if dg_warnings else "PASS", warnings=dg_warnings).to_dict())
    warnings.extend(dg_warnings)

    # 5. liquidity_gate
    liquidity_gate = _evaluate_liquidity_gate(candidate, symbol_meta, scan_rules, manifest=manifest)
    human_checks.extend(liquidity_gate["human_checks"])
    sub_gates.append(SubGateResult(
        gate="liquidity_gate",
        status=liquidity_gate["status"],
        blockers=liquidity_gate["blockers"],
        warnings=liquidity_gate["warnings"],
    ).to_dict())
    blockers.extend(liquidity_gate["blockers"])
    warnings.extend(liquidity_gate["warnings"])

    # 6. paper_eligibility_gate
    paper_eligibility = _resolve_paper_eligibility(
        candidate,
        identity_gate,
        liquidity_gate,
        dg_warnings,
        hg_warnings,
        ig_blockers,
    )
    sub_gates.append(SubGateResult(
        gate="paper_eligibility_gate",
        status=paper_eligibility["gate_status"],
        blockers=paper_eligibility["blockers"],
        warnings=paper_eligibility["warnings"],
    ).to_dict())
    blockers.extend(paper_eligibility["blockers"])
    warnings.extend(paper_eligibility["warnings"])
    paper_eligibility = {
        "status": paper_eligibility["status"],
        "reason_codes": paper_eligibility["reason_codes"],
        "owner_override_allowed": paper_eligibility["owner_override_allowed"],
    }
    
    missing = _run_missing_fields(candidate)
    if blockers:
        status = "BLOCK"
    elif warnings or missing:
        status = "WARN"
    else:
        status = "PASS"

    return QualityGateResult(
        status=status,
        blockers=blockers,
        warnings=warnings,
        missing_fields=missing,
        required_human_checks=human_checks,
        sub_gates=sub_gates,
        paper_eligibility=paper_eligibility
    ).to_dict()


def build_prompt_package(
    candidate: dict,
    run_info: dict,
    manifest: dict,
    symbol_meta: dict,
    scan_rules: dict,
    deep_research_contract: dict,
    risk_presets: dict,
    snapshot_rows: list[dict],
    mode: Optional[str] = None,
    generated_at_utc: Optional[str] = None,
) -> dict:
    """构建 DeepResearchPromptPackage v1 结构化字典。

    P1: mode 必须显式传入。
    P0: 有效 cutoff 严格语义。
    P1: 纯函数，不读文件。
    """
    # ---- P1: mode 验证 ----
    if mode is None or str(mode).strip() == "":
        raise ValueError("mode must be explicitly provided: HISTORICAL_REPLAY or PROSPECTIVE_LIVE")
    mode = str(mode).strip().upper()
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}. Must be one of {VALID_MODES}")

    if generated_at_utc is None:
        generated_at_utc = datetime.now(timezone.utc).isoformat()

    scan_time_utc = str(candidate.get("scan_time_utc", ""))

    # ---- P0: 解析有效 cutoff ----
    manifest_data_cutoff = manifest.get("data_cutoff")
    effective_cutoff_ms, cutoff_blockers = _resolve_effective_cutoff(
        scan_time_utc, manifest_data_cutoff
    )

    # ---- P0: 时间标准化 + cutoff 过滤 ----
    safe_rows: list[dict] = []
    ts_conflict_errors: list[str] = []
    for row in snapshot_rows:
        try:
            normalized = _normalize_snapshot_row(row)
            safe_rows.append(normalized)
        except ValueError as e:
            ts_conflict_errors.append(str(e))

    filtered_rows, enforce_blockers = _enforce_cutoff(safe_rows, effective_cutoff_ms)
    all_cutoff_blockers = cutoff_blockers + ts_conflict_errors + enforce_blockers

    # ---- 质量闸（含全部 cutoff/integrity 校验）----
    # all_cutoff_blockers 已包含所有完整性异常，每类只出现一次。
    qg = evaluate_quality_gate(
        candidate, run_info, manifest, symbol_meta, scan_rules, mode,
        cutoff_blockers=all_cutoff_blockers,
    )

    # 注入 cutoff 后行阻断（已在 evaluate_quality_gate 中处理为 BLOCK）

    # ---- 信号解释 ----
    trigger_items = build_signal_explanations(candidate, scan_rules)

    # ---- 市场快照（仅安全行）----
    target_snap = _market_snapshot_from_safe_rows(filtered_rows, candidate.get("symbol"))
    btc_snap = _market_snapshot_from_safe_rows(filtered_rows, "BTCUSDT")

    t_ret = target_snap.get("ret_24h_pct")
    b_ret = btc_snap.get("ret_24h_pct")
    excess_24h_val = (t_ret - b_ret) if (t_ret is not None and b_ret is not None) else None

    # funding display
    funding_val = _safe_float(candidate.get("funding_rate_8h"))
    funding_display = _funding_display(funding_val)

    # ranking
    ranking_method = (
        "abs(excess_move_pct_24h) 降序，异常审查排序；"
        "非综合 alpha 分数，不产 Long/Short 结论"
    )
    no_direction_claim = True

    # mandatory sections
    mandatory_research_sections = deep_research_contract.get("mandatory_research_sections", [
        "1. 标的/合约身份、迁移历史与交易所状态核验",
        "2. 截止时点前的关键事件时间线",
        "3. 数据真实性与跨市场一致性核查",
        "4. 市场 beta、板块 beta 与 BTC 相对表现分析",
        "5. 衍生品市场拥挤度：资金费率、OI 变化、缺失项说明",
        "6. 流动性、执行风险、可证伪条件与 No Trade 证据",
        "7. 结构化 verdict 与 Owner checklist",
    ])

    # prohibited actions
    prohibited_actions = deep_research_contract.get("prohibited_actions", [
        "不得替 Owner 决定 Long/Short",
        "不得要求生成或建议入场 / 出场价格",
        "不得要求生成或修改止损 / 止盈参数",
        "不得生成或修改任何 return tape 或评估结论",
        "不得将历史回放结果直接用于实盘绩效",
        "不得假设未经过事后核验的数据为真实数据",
        "不得复活 GRAVEYARD.md 所列已证伪方向（carry/庄家-费率/跟随聪明钱/机械方向择时）作为交易机制建议",
    ])

    # expected output
    expected_output = deep_research_contract.get("expected_output", {})
    expected_output_schema = {
        "schema_version": "v1",
        "sections": expected_output.get("required_fields", {}),
        "overall_evidence_allowed": expected_output.get("overall_evidence", {}).get("allowed", []),
        "source_urls_required": True,
        "published_at_required": True,
        "no_trade_action": True,
    }

    # risk policy reference
    risk_policy_reference = {
        "schema_version": "v1",
        "preset_version": str(risk_presets.get("preset_version", "DRAFT")),
        "default_preset_id": "standard",
        "status": str(risk_presets.get("status", "DRAFT")),
        "scope": str(risk_presets.get("scope", "PAPER_ONLY")),
        "common_discipline": risk_presets.get("common_discipline", []),
        "presets": [
            {
                "id": k,
                **v
            }
            for k, v in risk_presets.get("presets", {}).items()
        ]
    }

    # candidate_metrics
    candidate_metrics = _build_candidate_metrics(candidate, target_snap, btc_snap)

    # checkpoint hash（覆盖 manifest/effective cutoff）
    checkpoint_payload = {
        "run_id": run_info.get("run_id", candidate.get("run_id", "")),
        "record_id": candidate.get("record_id", ""),
        "scan_time_utc": scan_time_utc,
        "market_data_cutoff": manifest_data_cutoff,
        "effective_market_data_cutoff": effective_cutoff_ms,
        "snapshot_sha256": manifest.get("snapshot_sha256"),
        "mode": mode,
    }
    input_fingerprint = _compute_package_hash(checkpoint_payload)
    checkpoint_hash = input_fingerprint

    package_dict: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package_id": _make_package_id(
            run_info.get("run_id", ""), candidate.get("record_id", ""), generated_at_utc
        ),
        "template_version": TEMPLATE_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generated_at_utc": generated_at_utc,
        "run_id": run_info.get("run_id", candidate.get("run_id", "")),
        "record_id": candidate.get("record_id", ""),
        "symbol": candidate.get("symbol", ""),
        "scan_time_utc": scan_time_utc,
        "market_data_cutoff": manifest_data_cutoff,
        "effective_market_data_cutoff": effective_cutoff_ms,
        "snapshot_sha256": manifest.get("snapshot_sha256"),
        "mode": mode,
        "run_status": run_info.get("status", ""),
        "eligible_for_judgment": bool(run_info.get("eligible_for_judgment", False)),
        "eligible_for_paper": str(candidate.get("eligible_for_paper", "")),
        "quality_gate": qg,
        "ranking_method": ranking_method,
        "trigger_items": trigger_items,
        "no_direction_claim": no_direction_claim,
        "target_market_snapshot": {
            **target_snap,
            "funding_display": funding_display,
        },
        "btc_market_snapshot": btc_snap,
        "excess_24h": {
            "excess_move_pct_24h": _safe_float(candidate.get("excess_move_pct_24h")),
            "abs_excess_move_pct_24h": abs(_safe_float(candidate.get("excess_move_pct_24h")) or 0),
            "target_ret_24h_pct": t_ret,
            "btc_ret_24h_pct": b_ret,
            "note": "按 abs(excess_move_pct_24h) 降序排列；此排序仅用于异常审查，不代表综合 alpha 分数",
        },
        "candidate_metrics": candidate_metrics,
        "mandatory_research_sections": mandatory_research_sections,
        "competition_hypotheses": [
            "continuation（延续）",
            "reversal（反转）",
            "mean_reversion（均值回归）",
            "data_artifact（数据异常 / 假信号）",
        ],
        "prohibited_actions": prohibited_actions,
        "expected_output_schema": expected_output_schema,
        "risk_policy_reference": risk_policy_reference,
        "checkpoint_hash": checkpoint_hash,
        "historical_replay_qualitative_only": mode == "HISTORICAL_REPLAY",
        "input_fingerprint": input_fingerprint,
    }

    content_payload = {k: v for k, v in package_dict.items() if k not in ("content_hash", "artifact_hash", "package_hash", "input_fingerprint", "checkpoint_hash")}
    content_hash = _compute_package_hash(content_payload)
    
    artifact_payload = {**content_payload, "content_hash": content_hash, "input_fingerprint": input_fingerprint}
    artifact_hash = _compute_package_hash(artifact_payload)
    
    package_dict["content_hash"] = content_hash
    package_dict["artifact_hash"] = artifact_hash
    package_dict["package_hash"] = content_hash
    
    return package_dict


def render_research_prompt(
    package: dict,
    template_text: Optional[str] = None,
) -> str:
    """将 DeepResearchPromptPackage 渲染为确定性中文深研提示词。"""
    if template_text:
        return _render_with_template(package, template_text)
    return _render_default_prompt(package)


def _render_default_prompt(package: dict) -> str:
    mode = package.get("mode", "UNKNOWN")
    symbol = package.get("symbol", "?")
    record_id = package.get("record_id", "?")
    generated_at = package.get("generated_at_utc", "?")
    pkg_id = package.get("package_id", "?")
    ranking_method = package.get("ranking_method", "")
    no_dir = package.get("no_direction_claim", True)

    qg = package.get("quality_gate", {})
    qg_status = qg.get("status", "UNKNOWN")
    qg_blockers = qg.get("blockers", [])
    qg_warnings = qg.get("warnings", [])
    qg_missing = qg.get("missing_fields", [])

    trigger_items = package.get("trigger_items", [])

    t_snap = package.get("target_market_snapshot", {})
    b_snap = package.get("btc_market_snapshot", {})
    excess = package.get("excess_24h", {})

    funding_display = t_snap.get("funding_display", {})
    fd_val = funding_display.get("funding_rate_8h_decimal")

    mandatory = package.get("mandatory_research_sections", [])
    prohibited = package.get("prohibited_actions", [])
    output_schema = package.get("expected_output_schema", {})
    risk_ref = package.get("risk_policy_reference", {})

    cutoff = package.get("market_data_cutoff")
    eff_cutoff = package.get("effective_market_data_cutoff")
    cutoff_str = (
        datetime.fromtimestamp(int(cutoff) / 1000, tz=timezone.utc).isoformat()
        if cutoff else "N/A"
    )
    eff_cutoff_str = (
        datetime.fromtimestamp(int(eff_cutoff) / 1000, tz=timezone.utc).isoformat()
        if eff_cutoff else "N/A"
    )
    run_status = package.get("run_status", "")

    parts: list[str] = []

    parts.append("=" * 70)
    parts.append("【系统指令】你是一名独立加密资产研究分析师，正在为以下候选标的进行深度研究。")
    parts.append(f"研究包 ID：{pkg_id}")
    parts.append(f"生成时间（UTC）：{generated_at}")
    parts.append(f"模式：{mode}")
    parts.append(f"记录 ID：{record_id}")
    parts.append("=" * 70)

    parts.append("\n【重要声明】")
    parts.append(
        "本提示词包由 AlphaHive 自动筛选基建模块生成，"
        "不包含 Long/Short 结论，不产出入场/出场价格建议，"
        "不对任何交易方向做判断。"
    )
    if no_dir:
        parts.append("no_direction_claim = true：你不应在此研究包中产生任何方向性结论。")
    parts.append(f"排名方法：{ranking_method}")

    parts.append(f"\n【质量闸状态】{qg_status}")
    if qg_blockers:
        parts.append("【阻断项】")
        for b in qg_blockers:
            parts.append(f"  ✗ {b}")
    if qg_warnings:
        parts.append("【警告项】")
        for w in qg_warnings:
            parts.append(f"  ⚠ {w}")
    if qg_missing:
        parts.append("【缺失字段】")
        for m in qg_missing:
            parts.append(f"  — {m}（显示为 null/未提供，不是 0）")
    if qg_status == "BLOCK":
        parts.append("【注意】质量闸已阻断，请在报告中说明阻断原因并建议是否等待下一扫描周期。")

    parts.append(f"\n【候选标的】{symbol}")
    parts.append(f"run_id：{package.get('run_id', '?')}")
    parts.append(f"run 状态：{run_status}")
    parts.append(f"市场数据截止（cutoff）：{cutoff_str}")
    parts.append(f"有效市场数据截止（effective cutoff）：{eff_cutoff_str}")
    parts.append(f"快照 SHA-256：{package.get('snapshot_sha256', 'N/A')}")
    parts.append(f"历史回放仅限质性研究：{package.get('historical_replay_qualitative_only', False)}")

    parts.append("\n" + "-" * 50)
    parts.append("【触发信号解释】")
    parts.append("-" * 50)
    for t in trigger_items:
        impl_tag = "✅ 已实现" if t.get("implementation_status") == "COMPUTED" else "⏸ 未实现"
        trig_tag = " [本次已触发]" if t.get("triggered") else ""
        parts.append(f"\n[{t.get('code', '?')}] {t.get('label_zh', '?')} [{impl_tag}]{trig_tag}")
        parts.append(f"  说明：{t.get('explanation_zh', t.get('description', '?'))}")
        obs = t.get("observation")
        if obs is not None:
            parts.append(f"  观测值：{obs} {t.get('unit', '')}")
        else:
            parts.append(f"  观测值：未计算")
        thr = t.get("threshold")
        if thr is not None:
            parts.append(f"  阈值：{thr}")
        parts.append(f"  局限：{t.get('limitation_zh', t.get('limitation', '?'))}")

    parts.append("\n" + "-" * 50)
    parts.append("【市场快照（截止 cutoff 前最后一根完整 K 线）】")
    parts.append("-" * 50)
    parts.append(f"\n标的 {symbol}：")
    if t_snap.get("last_close"):
        parts.append(f"  最新价：{t_snap['last_close']}  24h 收益：{t_snap.get('ret_24h_pct', 'N/A')}%")
        parts.append(f"  最高：{t_snap.get('last_high')}  最低：{t_snap.get('last_low')}  成交额 24h：{t_snap.get('last_turnover_usd', 'N/A')} USD")
    else:
        parts.append("  价格数据：未提供")

    if fd_val is not None:
        parts.append(f"  Funding（decimal）：{fd_val}  Funding（percent）：{funding_display.get('funding_rate_8h_percent')}%  [校验：{funding_display.get('validation_status')}]")
    else:
        parts.append("  Funding：未提供")

    oi_val = t_snap.get("open_interest")
    parts.append(f"  OI：{'未提供' if oi_val is None else oi_val}")
    parts.append(f"  最后完整 K 线时间戳：{t_snap.get('last_complete_bar_timestamp_utc', 'N/A')}")

    parts.append(f"\nBTCUSDT 基准：")
    if b_snap.get("last_close"):
        parts.append(f"  最新价：{b_snap['last_close']}  24h 收益：{b_snap.get('ret_24h_pct', 'N/A')}%")
    else:
        parts.append("  价格数据：未提供")

    parts.append(f"\n超额 24h 收益（标的 − BTC）：{excess.get('excess_move_pct_24h', 'N/A')}%")

    parts.append("\n" + "-" * 50)
    parts.append("【强制研究章节（请按顺序完成）】")
    parts.append("-" * 50)
    for section in mandatory:
        parts.append(f"  {section}")

    parts.append("\n【竞争假设（四个均需评估）】")
    for h in ["continuation（延续）", "reversal（反转）", "mean_reversion（均值回归）", "data_artifact（数据异常 / 假信号）"]:
        parts.append(f"  • {h}")

    parts.append("\n【禁止动作】")
    for p in prohibited:
        parts.append(f"  ✗ {p}")

    parts.append("\n" + "-" * 50)
    parts.append("【结构化输出要求】")
    parts.append("-" * 50)
    parts.append(f"请按以下 JSON Schema 输出（JSON 格式，不要 Markdown 围栏）：\n")
    parts.append(json.dumps(output_schema, ensure_ascii=False, indent=2))

    parts.append(f"\n【风险策略参考】")
    parts.append(f"  preset_version：{risk_ref.get('preset_version', 'N/A')}")
    parts.append(f"  scope：{risk_ref.get('scope', 'N/A')}")
    parts.append(f"  note：{risk_ref.get('note', '')}")

    parts.append("\n【Owner 核查清单（请填写）】")
    for item in [
        "标的身份与合约迁移核验完毕",
        "截止时点前的关键事件时间线已确认",
        "数据来源 URL 与发布时间均已记录",
        "衍生品拥挤度（funding/OI）已评估",
        "四个竞争假设各有证据支持/反对",
        "流动性风险与执行可行性已评估",
        "可证伪条件与 No Trade 证据已列出",
        "结构化 verdict 与 Owner checklist 已完成",
        "研究结论不含任何 Long/Short 或入场建议",
    ]:
        parts.append(f"  □ {item}")

    return "\n".join(parts)


def _render_with_template(package: dict, template_text: str) -> str:
    mapping = {
        "{{symbol}}": package.get("symbol", "?"),
        "{{record_id}}": package.get("record_id", "?"),
        "{{generated_at_utc}}": package.get("generated_at_utc", "?"),
        "{{mode}}": package.get("mode", "?"),
        "{{quality_gate_status}}": package.get("quality_gate", {}).get("status", "?"),
    }
    result = template_text
    for k, v in mapping.items():
        result = result.replace(k, str(v))
    return result


def hash_prompt_package(package: dict) -> str:
    content_payload = {k: v for k, v in package.items() if k not in ("content_hash", "artifact_hash", "package_hash", "input_fingerprint", "checkpoint_hash")}
    return _compute_package_hash(content_payload)
