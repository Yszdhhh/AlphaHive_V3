r"""222 — aggTrades 缓存垃圾回收（控制 data/aggTrades_cache 体量）。

默认保留最近 --keep-days 天修改的文件；其余删除。
用法：
  python scripts/222_aggtrades_cache_gc.py --dry-run
  python scripts/222_aggtrades_cache_gc.py --keep-days 30
  python scripts/222_aggtrades_cache_gc.py --keep-days 14 --max-mb 800
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE = PROJECT_ROOT / "data" / "aggTrades_cache"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-days", type=int, default=30)
    ap.add_argument("--max-mb", type=float, default=0, help=">0 时再按总大小从旧到新删到阈值")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not CACHE.exists():
        print(f"no cache {CACHE}")
        return 0
    now = time.time()
    cutoff = now - args.keep_days * 86400
    files = [p for p in CACHE.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    print(f"cache files={len(files)} size_mb={total/1e6:.1f} keep_days={args.keep_days}")

    to_del = [p for p in files if p.stat().st_mtime < cutoff]
    # max-mb: 继续从最旧删
    if args.max_mb > 0:
        remain = [p for p in files if p not in to_del]
        size = sum(p.stat().st_size for p in remain)
        for p in files:
            if size / 1e6 <= args.max_mb:
                break
            if p not in to_del:
                to_del.append(p)
                size -= p.stat().st_size

    freed = sum(p.stat().st_size for p in to_del)
    print(f"delete {len(to_del)} files free_mb={freed/1e6:.1f} dry={args.dry_run}")
    for p in to_del:
        if args.dry_run:
            print(f"  would del {p.relative_to(CACHE)}")
        else:
            p.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
