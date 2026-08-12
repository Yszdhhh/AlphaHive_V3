r"""224 — 周度数据/基建同步（一条命令）。

顺序：
  1) 218 klines 增量回补（并硬链 raw）
  2) 110 funding 历史刷新
  3) 221 klines 硬链接去重
  4) 222 aggTrades 缓存 GC（默认 keep 7d + max 500MB）
  5) 220 覆盖报告
  6) 199 健康检查

用法：
  python scripts/224_weekly_data_sync.py
  python scripts/224_weekly_data_sync.py --skip-backfill   # 只报告+GC
  python scripts/224_weekly_data_sync.py --no-gc
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "weekly_data_sync.md"
PY = sys.executable


def run(label: str, args: list[str]) -> tuple[int, str]:
    print(f"\n=== {label} ===")
    proc = subprocess.run(
        [PY, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    # tail for log
    tail = "\n".join(out.splitlines()[-30:])
    print(tail)
    return proc.returncode, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-backfill", action="store_true")
    ap.add_argument("--no-gc", action="store_true")
    ap.add_argument("--keep-days", type=int, default=7)
    ap.add_argument("--max-mb", type=float, default=500)
    args = ap.parse_args()

    steps: list[tuple[str, list[str]]] = []
    if not args.skip_backfill:
        steps.append(("218 klines backfill", ["scripts/218_backfill_binance_klines.py"]))
        steps.append(("110 funding backfill", ["scripts/110_backfill_history.py"]))
    steps.append(("221 hardlink dedupe", ["scripts/221_dedupe_klines_hardlink.py"]))
    if not args.no_gc:
        steps.append(
            (
                "222 aggTrades GC",
                [
                    "scripts/222_aggtrades_cache_gc.py",
                    f"--keep-days={args.keep_days}",
                    f"--max-mb={args.max_mb}",
                ],
            )
        )
    steps.append(("220 coverage", ["scripts/220_coverage_gap_report.py"]))
    steps.append(("199 health", ["scripts/199_data_health.py"]))

    results = []
    worst = 0
    for label, cmd in steps:
        code, out = run(label, cmd)
        results.append((label, code, "\n".join(out.splitlines()[-8:])))
        if code != 0:
            worst = code

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 周度数据同步 224\n",
        f"- date: {now}",
        f"- skip_backfill: {args.skip_backfill}  no_gc: {args.no_gc}",
        f"- keep_days={args.keep_days} max_mb={args.max_mb}\n",
        "| 步骤 | exit |",
        "|---|---|",
    ]
    for label, code, _ in results:
        lines.append(f"| {label} | {code} |")
    lines.append("\n## tails\n")
    for label, code, tail in results:
        lines.append(f"### {label} (exit {code})\n```\n{tail}\n```\n")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {REPORT} worst_exit={worst}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
