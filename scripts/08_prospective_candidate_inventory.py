"""Print the read-only prospective candidate inventory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from harness.lib.prospective_candidate_inventory import inspect_prospective_candidates


def main() -> None:
    result = inspect_prospective_candidates(
        PROJECT_ROOT / "harness" / "runs",
        PROJECT_ROOT / "harness" / "run_registry.yaml",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
