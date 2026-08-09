r"""203_api_usage.py — API 用量报告（Dune 实时 + Coinalyze 本地计数 + 注册表）。

回答"配了哪些 API、免费 limit 多少、用了多少"：
- Dune：MCP getUsage 实时（creditsUsed/quota）
- Coinalyze：本地计数（196 sync 日志里的批次数 × 每批 symbol 数）
- 其余：注册表静态额度（无用量 API，标注不可见）
输出：reports/api_usage.md + stdout
用法：python scripts/203_api_usage.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REPORT = PROJECT_ROOT / "reports" / "api_usage.md"
REGISTRY = PROJECT_ROOT / "config" / "api_registry.yaml"


def dune_usage() -> str:
    try:
        from harness.lib.dune_mcp import DuneMCP
        d = DuneMCP()
        d.initialize()
        r = d.get_usage()
        for c in r.get("content", []):
            if c.get("type") == "text":
                obj = json.loads(c["text"])
                return (f"{obj['creditsUsed']:.2f} / {obj['creditsQuota']} credits "
                        f"（{obj['billingPeriodStart'][:10]} ~ {obj['billingPeriodEnd'][:10]}）")
    except Exception as exc:  # noqa: BLE001
        return f"查询失败: {exc}"
    return "-"


def coinalyze_usage() -> str:
    """196 sync 日志累计：每批 1 次请求 × 批内 symbol 数（每 symbol 计 1 call）。"""
    log = PROJECT_ROOT / "reports" / "coinalyze_sync_log.txt"
    if not log.exists():
        return "无同步日志（尚未运行定时任务）"
    txt = log.read_text(encoding="utf-8", errors="ignore")
    calls = 0
    runs = txt.count("[194] pulling")
    for m in re.finditer(r"\[194\] pulling (\d+) symbols", txt):
        calls += int(m.group(1))
    return f"累计 {calls} calls（{runs} 次同步）"


def main() -> int:
    with REGISTRY.open("r", encoding="utf-8") as f:
        reg = yaml.safe_load(f)["apis"]
    dune = dune_usage()
    coinalyze = coinalyze_usage()

    lines = ["# API 用量报告（203）\n",
             f"- 生成：{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"- Dune（实时）: {dune}",
             f"- Coinalyze（本地计数）: {coinalyze}\n",
             "| API | key 位置 | 免费 limit | 用量 | 用途 |",
             "|---|---|---|---|---|"]
    for name, a in reg.items():
        usage = "实时: " + dune if name == "dune" else ("本地: " + coinalyze if name == "coinalyze" else "不可见")
        lines.append(f"| {name} | {a['key']} | {a['free_limit']} | {usage} | {a['purpose']} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
