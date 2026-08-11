"""Run a shadow task, then notify Hermes Feishu without masking its exit code."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTIFIER = ROOT / "scripts" / "alphahive_feishu_notify.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["scan", "forward", "paper"], required=True)
    ap.add_argument("script")
    args = ap.parse_args()
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / args.script)],
                          cwd=ROOT, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    notify = subprocess.run(
        [sys.executable, str(NOTIFIER), args.kind,
         "--exit-code", str(proc.returncode), "--stderr", proc.stderr[-3000:]],
        cwd=ROOT, capture_output=True, text=True,
    )
    if notify.stdout:
        print(notify.stdout, end="")
    if notify.stderr:
        print(notify.stderr, end="", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
