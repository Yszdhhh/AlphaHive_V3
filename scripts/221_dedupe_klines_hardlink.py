r"""221 — 去掉 history/klines 与 raw_1h/klines 双份占用（硬链接）。

canonical = history/klines/{SYM}.parquet
raw_1h/klines/{SYM}.parquet → 同 inode 硬链接（同盘、内容一致时）

Windows/NTFS 同卷可用。幂等：已是同一文件则跳过。
用法：python scripts/221_dedupe_klines_hardlink.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.data_registry import paths  # noqa: E402

DB = Path(str(paths.binance_free.raw_1h)).parent
HIST = DB / "history" / "klines"
RAW = Path(str(paths.binance_free.raw_1h)) / "klines"


def same_content(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    # 快速：前 64KB + 后 64KB
    with a.open("rb") as fa, b.open("rb") as fb:
        if fa.read(65536) != fb.read(65536):
            return False
        sa, sb = a.stat().st_size, b.stat().st_size
        if sa > 131072:
            fa.seek(sa - 65536)
            fb.seek(sb - 65536)
            if fa.read(65536) != fb.read(65536):
                return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not HIST.exists():
        print(f"missing {HIST}; run 218 first")
        return 1
    RAW.mkdir(parents=True, exist_ok=True)
    linked = skipped = failed = 0
    for hp in sorted(HIST.glob("*.parquet")):
        rp = RAW / hp.name
        try:
            if rp.exists():
                # 已是同一 inode？
                if os.path.samefile(hp, rp):
                    skipped += 1
                    continue
                if not same_content(hp, rp):
                    print(f"DIFF content, keep both: {hp.name}")
                    failed += 1
                    continue
                if args.dry_run:
                    print(f"would link {rp.name}")
                    linked += 1
                    continue
                rp.unlink()
            else:
                if args.dry_run:
                    print(f"would create link {rp.name}")
                    linked += 1
                    continue
            os.link(hp, rp)
            linked += 1
            print(f"linked {hp.name}")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {hp.name}: {e}")
            failed += 1
    print(f"done linked={linked} skipped_same={skipped} failed={failed} dry={args.dry_run}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
