r"""199_data_health.py — 数据源健康监控（U1/U7：跨源一致性监控）。

背景：数据源停更靠人肉发现（coinglass klines 停 07-07、衍生停 06-23 都是事后才知）。
本脚本用 data_registry 统一路径 + 新鲜度检查，输出全部注册源的健康报告：
- 每源：存在性、最后 bar 时间、距今小时、是否过期（阈值 per 源）
- 已知停更源标 KNOWN_STALE（coinglass 衍生维度）区分"预期停更"与"意外过期"
- 新增源只需在 data_registry.health_report() 或本脚本加一行

输出：reports/data_health.md + stdout
用法：python scripts/199_data_health.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_registry import health_report  # noqa: E402

REPORT = PROJECT_ROOT / "reports" / "data_health.md"

# 预期停更（数据源官方断供，非故障）：停更 → 不告警
KNOWN_STALE = {
    "coinglass_klines": "coinglass 公共接口 klines 停于 2026-07-07（记忆：klines 实际到 07-07）",
    "coinglass_liquidation": "coinglass 清算停于 2026-06-23，E21 前向已切 Coinalyze（196）",
}


def main() -> int:
    rep = health_report()
    now = datetime.now(timezone.utc)
    lines = ["# 数据源健康报告（199）\n",
             f"- 生成：{now:%Y-%m-%d %H:%M} UTC",
             f"- 来源：config/data_paths.yaml + harness/lib/data_registry.py\n",
             "| 源 | 存在 | 最后 bar | 距今(h) | 状态 |",
             "|---|---|---|---|---|"]
    problems = 0
    for name, r in rep.items():
        if not r.get("exists"):
            status = "❌ 缺失"
            problems += 1
        elif r.get("stale"):
            note = KNOWN_STALE.get(name, "")
            status = f"⚠️ 过期{'（预期停更：' + note + '）' if note else ''}"
            if not note:
                problems += 1
        else:
            status = "✅ 正常"
        lines.append(f"| {name} | {'✓' if r.get('exists') else '✗'} | {r.get('last') or '-'} | "
                     f"{r.get('age_h') if r.get('age_h') is not None else '-'} | {status} |")
    lines.append(f"\n**意外过期源：{problems} 个**（预期停更不计）")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
