"""
Signal Review Exporter — 从最新 clean V3 run 生成信号审查包。

纯函数 + 文件写入，不访问交易所/LLM/真实交易。
输出：signal_review/latest.json + 历史 JSON + notification_outbox.jsonl
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ALPHA_HIVE_ROOT = Path(__file__).resolve().parents[3] / "alpha_hive"
V3_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = V3_ROOT / "harness" / "runs"
RESULTS_DIR = ALPHA_HIVE_ROOT / "results" / "signal_review"
CONFIG_DIR = V3_ROOT / "config"

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


def _compute_notification_key(entry: dict) -> str:
    """计算稳定的 notification_key。

    包含 record_id、snapshot_sha256、template_version 和信号/市场内容哈希。
    不包含纯导出时间，确保相同数据重复导出不重复入队。
    """
    pkg = entry.get("package", {})
    brief = entry.get("briefing", {})

    # 稳定内容：触发信号 + 市场快照指标 + 质量闸状态
    stable_payload = {
        "record_id": entry.get("record_id", ""),
        "snapshot_sha256": entry.get("snapshot_sha256", ""),
        "template_version": entry.get("template_version", ""),
        "quality_status": entry.get("quality_status", ""),
        "triggered_codes": sorted([
            t.get("code", "") for t in brief.get("triggered_triggers", [])
        ]),
        "metrics_summary": brief.get("metrics_summary", {}),
        "blockers": sorted(brief.get("blockers", [])),
        "warnings": sorted(brief.get("warnings", [])),
    }

    raw = json.dumps(stable_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """Load YAML file. Falls back to JSON if pyyaml unavailable."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8-sig") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # pyyaml not installed — try JSON fallback
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def _load_csv_rows(path: Path) -> list[dict]:
    """Load CSV file into list of dicts."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_clean_run() -> Optional[Path]:
    """找到最新可用 run 目录。

    判断逻辑：manifest 无 status 字段或 status == "clean" 均视为可用。
    """
    if not RUNS_DIR.exists():
        return None

    run_dirs = []
    for d in RUNS_DIR.iterdir():
        if not d.is_dir():
            continue
        manifest_path = d / "run_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _load_json(manifest_path)
        status = manifest.get("status")
        if status == "clean":
            run_dirs.append((d.name, d))

    if not run_dirs:
        return None

    run_dirs.sort(key=lambda x: x[0], reverse=True)
    return run_dirs[0][1]


def load_run_data(run_dir: Path) -> dict[str, Any]:
    """加载单个 run 的所有数据。"""
    manifest = _load_json(run_dir / "run_manifest.json")
    candidates = _load_csv_rows(run_dir / "candidates.csv")
    symbol_meta_rows = _load_csv_rows(run_dir / "symbol_meta.csv")
    snapshot_rows = _load_csv_rows(run_dir / "input_snapshot.csv")

    # symbol_meta: 转为 symbol -> meta 的映射
    symbol_meta = {}
    for row in symbol_meta_rows:
        sym = row.get("symbol", "")
        if sym:
            symbol_meta[sym] = row

    import hashlib
    def _file_hash(path: Path) -> Optional[str]:
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    hashes = {
        "input_snapshot_sha256": _file_hash(run_dir / "input_snapshot.csv"),
        "symbol_meta_sha256": _file_hash(run_dir / "symbol_meta.csv"),
        "return_tape_sha256": _file_hash(run_dir / "return_tape.csv"),
    }

    return {
        "manifest": manifest,
        "candidates": candidates,
        "symbol_meta": symbol_meta,
        "snapshot_rows": snapshot_rows,
        "run_dir": run_dir,
        "hashes": hashes,
    }


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def load_configs() -> dict[str, Any]:
    """加载 V3 配置文件。"""
    scan_rules = _load_yaml(CONFIG_DIR / "scan_rules.yaml")
    contract = _load_yaml(CONFIG_DIR / "deep_research_contract.yaml")
    presets = _load_yaml(CONFIG_DIR / "paper_execution_presets.yaml")
    return {
        "scan_rules": scan_rules,
        "deep_research_contract": contract,
        "risk_presets": presets,
    }


# ---------------------------------------------------------------------------
# 核心：构建信号审查包
# ---------------------------------------------------------------------------

def _strip_denylist(data: dict) -> dict:
    """移除 denylist 字段。"""
    return {k: v for k, v in data.items() if k not in DENYLIST_FIELDS}


def _build_signal_review_entry(
    candidate: dict,
    run_info: dict,
    manifest: dict,
    symbol_meta: dict,
    scan_rules: dict,
    deep_research_contract: dict,
    risk_presets: dict,
    snapshot_rows: list[dict],
    rank: int,
) -> dict[str, Any]:
    """为单个候选构建信号审查条目。"""
    from deep_research_package import build_prompt_package, render_research_prompt

    # 候选字段类型转换（CSV 全是字符串）
    candidate_typed = dict(candidate)
    for key in ("rank", "turnover_24h_usd", "trigger_value", "trigger_quantile",
                "abs_move_pct_24h", "excess_move_pct_24h", "funding_rate_8h",
                "oi_change_pct_24h"):
        val = candidate_typed.get(key, "")
        if val == "" or val is None:
            candidate_typed[key] = None
        else:
            try:
                candidate_typed[key] = float(val)
            except (ValueError, TypeError):
                candidate_typed[key] = None

    for key in ("large_move_flag_24h", "is_top_candidate"):
        val = candidate_typed.get(key, "")
        if isinstance(val, str):
            candidate_typed[key] = val.lower() in ("true", "1", "yes")

    # 构建 package
    package = build_prompt_package(
        candidate=candidate_typed,
        run_info=run_info,
        manifest=manifest,
        symbol_meta=symbol_meta,
        scan_rules=scan_rules,
        deep_research_contract=deep_research_contract,
        risk_presets=risk_presets,
        snapshot_rows=snapshot_rows,
        mode=manifest.get("mode"),
    )

    # 渲染 prompt
    rendered_prompt = render_research_prompt(package)

    # 构建简报字段（从 package 提取，确保信息完整）
    qg = package.get("quality_gate", {})
    trigger_items = package.get("trigger_items", [])
    metrics = package.get("candidate_metrics", {})

    # 筛选已触发的 trigger 用于简报
    triggered_triggers = [
        {
            "code": t.get("code"),
            "label": t.get("label_zh"),
            "observation": t.get("observation"),
            "threshold": t.get("threshold"),
            "unit": t.get("unit"),
            "explanation": t.get("explanation_zh"),
            "limitation": t.get("limitation_zh"),
        }
        for t in trigger_items
        if t.get("triggered")
    ]

    # 为什么被筛出
    why_screened = []
    if triggered_triggers:
        why_screened.append(
            f"触发 {len(triggered_triggers)} 个信号: " +
            ", ".join(t["code"] for t in triggered_triggers)
        )
    else:
        why_screened.append("无已触发信号（所有 trigger 均未触发或未计算）")

    # 数据缺失和人工检查项
    missing_fields = qg.get("missing_fields", [])
    blockers = qg.get("blockers", [])
    warnings = qg.get("warnings", [])
    human_checks = qg.get("required_human_checks", [])

    entry = {
        "priority_rank": rank,
        "symbol": package.get("symbol", ""),
        "quality_status": qg.get("status", "UNKNOWN"),
        "run_id": package.get("run_id", ""),
        "record_id": package.get("record_id", ""),
        "scan_time_utc": package.get("scan_time_utc", ""),
        "effective_market_data_cutoff": package.get("effective_market_data_cutoff"),
        "snapshot_sha256": package.get("snapshot_sha256"),
        "mode": package.get("mode", ""),
        "package_id": package.get("package_id", ""),
        "package_hash": package.get("package_hash", ""),
        "schema_version": package.get("schema_version", ""),
        "template_version": package.get("template_version", ""),

        # 简报字段
        "briefing": {
            "triggered_triggers": triggered_triggers,
            "why_screened": why_screened,
            "missing_fields": missing_fields,
            "blockers": blockers,
            "warnings": warnings,
            "human_checks": human_checks,
            "metrics_summary": {
                "symbol_return_24h_pct": metrics.get("symbol_return_24h_pct"),
                "btc_return_24h_pct": metrics.get("btc_return_24h_pct"),
                "excess_return_24h_pct": metrics.get("excess_return_24h_pct"),
                "realized_vol_24h_decimal": metrics.get("realized_vol_24h_decimal"),
                "turnover_24h_usd": metrics.get("turnover_24h_usd"),
                "funding_rate_8h_percent": metrics.get("funding_rate_8h_percent"),
                "oi_current": metrics.get("oi_current"),
                "last_complete_bar_timestamp_utc": metrics.get("last_complete_bar_timestamp_utc"),
            },
            "dashboard_deep_link": f"/app/review.html?run={package.get('run_id', '')}&record={package.get('record_id', '')}",
        },

        # 完整 package（strip denylist）
        "package": _strip_denylist(package),

        # rendered prompt
        "rendered_prompt": rendered_prompt,

        # paper plan form 默认状态
        "paper_plan_form": {
            "disabled": qg.get("status") == "BLOCK" or qg.get("eligible_for_paper") == "No",
            "disabled_reason": (
                f"质量状态为 {qg.get('status', 'UNKNOWN')}"
                if qg.get("status") == "BLOCK"
                else None
            ),
        },
    }

    return entry


def build_signal_review(
    run_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """构建完整信号审查结果。"""
    if run_dir is None:
        run_dir = find_latest_clean_run()
    if run_dir is None:
        raise RuntimeError("No clean run found")

    if output_dir is None:
        output_dir = RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    run_data = load_run_data(run_dir)
    configs = load_configs()

    manifest = run_data["manifest"]
    candidates = run_data["candidates"]
    symbol_meta = run_data["symbol_meta"]
    snapshot_rows = run_data["snapshot_rows"]

    run_info = {
        "run_id": manifest.get("run_id", ""),
        "status": manifest.get("status"),
        "eligible_for_judgment": manifest.get("eligible_for_judgment"),
        "hashes": run_data.get("hashes", {}),
    }

    # 按 abs(excess_move_pct_24h) 降序排列
    def _sort_key(c):
        val = c.get("excess_move_pct_24h", "")
        try:
            return abs(float(val)) if val else 0
        except (ValueError, TypeError):
            return 0

    sorted_candidates = sorted(candidates, key=_sort_key, reverse=True)

    entries = []
    for rank, cand in enumerate(sorted_candidates, 1):
        try:
            entry = _build_signal_review_entry(
                candidate=cand,
                run_info=run_info,
                manifest=manifest,
                symbol_meta=symbol_meta.get(cand.get("symbol", ""), {}),
                scan_rules=configs["scan_rules"],
                deep_research_contract=configs["deep_research_contract"],
                risk_presets=configs["risk_presets"],
                snapshot_rows=snapshot_rows,
                rank=rank,
            )
            entries.append(entry)
        except Exception as e:
            # 单个候选失败不影响其他候选
            entries.append({
                "priority_rank": rank,
                "symbol": cand.get("symbol", "?"),
                "quality_status": "BLOCK",
                "error": str(e),
                "briefing": {
                    "triggered_triggers": [],
                    "why_screened": [f"构建失败: {e}"],
                    "missing_fields": [],
                    "blockers": [f"build_error: {e}"],
                    "warnings": [],
                    "human_checks": [],
                    "metrics_summary": {},
                    "dashboard_deep_link": "",
                },
                "package": {},
                "rendered_prompt": "",
                "paper_plan_form": {"disabled": True, "disabled_reason": f"构建失败: {e}"},
            })

    # 排序后的风险 preset（用于前端）
    risk_presets_list = configs["risk_presets"].get("presets", {})

    result = {
        "meta": {
            "schema_version": "deep_research_prompt_package_v1",
            "run_id": manifest.get("run_id", ""),
            "scan_time_utc": manifest.get("scan_time_utc", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_candidates": len(entries),
            "ranking_method": "abs(excess_move_pct_24h) 降序",
            "ranking_note": "按异常强度排序，非综合 alpha 分数，不产 Long/Short 结论",
            "disclaimer": "异常筛选 ≠ 开单推荐；当前信号无方向结论",
        },
        "risk_presets": [
            {
                "id": pid,
                "label_zh": p.get("label_zh", pid),
                "validation_status": p.get("validation_status", "DRAFT"),
                "is_default": p.get("is_default", False),
                "paper_risk_per_trade_pct": p.get("paper_risk_per_trade_pct", 0),
                "max_open_portfolio_risk_pct": p.get("max_open_portfolio_risk_pct", 0),
                "take_profit_targets": p.get("take_profit_targets", []),
                "after_tp1": p.get("after_tp1", ""),
                "common_discipline": p.get("common_discipline", []),
            }
            for pid, p in risk_presets_list.items()
        ],
        "stop_distance_note": "止损距离 = MAX(结构失效距离+结构缓冲, 波动倍数×波动率, 成本地板倍数×摩擦成本)。具体数值等待后端计算，前端不硬编码。",
        "candidates": entries,
    }

    # ---- 原子写入 ----
    _atomic_write_json(output_dir / "latest.json", result)

    # 历史 JSON
    history_path = output_dir / f"{manifest.get('run_id', 'unknown')}.json"
    _atomic_write_json(history_path, result)

    # 通知 Outbox
    _write_notification_outbox(output_dir / "notification_outbox.jsonl", entries)

    return result


def _atomic_write_json(path: Path, data: dict) -> None:
    """使用临时文件 + 原子替换写入 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows: 目标文件存在时需要先删除
        if path.exists():
            path.unlink()
        os.rename(tmp_path, str(path))
    except Exception:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _write_notification_outbox(
    outbox_path: Path,
    entries: list[dict],
    max_notifications: int = 3,
) -> None:
    """写入通知 Outbox。按 notification_key 去重。

    notification_key 基于 record_id + snapshot_sha256 + template_version + 内容哈希，
    相同数据重复导出不重复入队；同 record_id 但数据变化时可产生新通知。
    """
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    if not outbox_path.exists():
        outbox_path.touch()

    # 读取已有 notification_keys
    existing_keys: set[str] = set()
    if outbox_path.exists():
        with open(outbox_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if "notification_key" in record:
                        existing_keys.add(record["notification_key"])
                except json.JSONDecodeError:
                    continue

    # 筛选新候选（非 BLOCK，且 notification_key 未入队）
    new_notifications = []
    for entry in entries:
        if len(new_notifications) >= max_notifications:
            break
        status = entry.get("quality_status", "")
        if status == "BLOCK":
            continue

        nkey = _compute_notification_key(entry)
        if nkey in existing_keys:
            continue

        new_notifications.append({
            "notification_key": nkey,
            "package_hash": entry.get("package_hash", ""),
            "symbol": entry.get("symbol", ""),
            "quality_status": status,
            "record_id": entry.get("record_id", ""),
            "run_id": entry.get("run_id", ""),
            "scan_time_utc": entry.get("scan_time_utc", ""),
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "notification_type": "signal_review_ready",
        })

    if new_notifications:
        with open(outbox_path, "a", encoding="utf-8") as f:
            for n in new_notifications:
                f.write(json.dumps(n, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    run_dir = RUNS_DIR / run_id if run_id else None
    result = build_signal_review(run_dir=run_dir)
    print(f"Exported {len(result['candidates'])} candidates from run {result['meta']['run_id']}")
    print(f"Output: {RESULTS_DIR / 'latest.json'}")
