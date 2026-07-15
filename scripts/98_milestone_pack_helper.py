"""Create and validate non-overwriting AlphaHive milestone packages."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


REQUIRED_DIRS = ("commit_diffs", "agent_outputs", "reports", "regression")
SECTIONS = (
    "Status",
    "Milestone outcome",
    "Regression evidence",
    "SELF_CHECK",
    "Provenance",
    "OWNER_DECISIONS_NEEDED",
    "Commit diff index",
)


def _desktop() -> Path:
    return Path.home() / "Desktop"


def _validate_new_output_dir(output_dir: Path, desktop: Path | None = None) -> Path:
    root = (desktop or _desktop()).resolve()
    resolved = output_dir.resolve()
    if resolved.parent != root:
        raise ValueError("output directory must be a direct child of Desktop")
    if not (resolved.name.startswith("AlphaHive_V3_") and resolved.name.endswith("_deliverables")):
        raise ValueError("output directory must match AlphaHive_V3_*_deliverables")
    if resolved.exists():
        raise FileExistsError(f"refusing to overwrite existing package: {resolved}")
    return resolved


def _template() -> str:
    parts = ["# AlphaHive V3 milestone deliverable", ""]
    for index, title in enumerate(SECTIONS, start=1):
        parts.extend((f"## {index}. {title}", "", "MISSING — fill by codex", ""))
    return "\n".join(parts)


def create_package(output_dir: Path, name: str, use_fallback: bool = False, desktop: Path | None = None) -> Path:
    target = _validate_new_output_dir(output_dir, desktop=desktop)
    target.mkdir(parents=True)
    for directory in REQUIRED_DIRS:
        (target / directory).mkdir()
    if use_fallback:
        (target / "pc_fallback").mkdir()
    (target / f"{name}_DELIVERABLE.md").write_text(_template(), encoding="utf-8")
    return target


def _section_content(document: str, index: int, title: str) -> str:
    marker = f"## {index}. {title}"
    if marker not in document:
        return ""
    after = document.split(marker, 1)[1]
    next_marker = f"## {index + 1}." if index < len(SECTIONS) else None
    return after.split(next_marker, 1)[0].strip() if next_marker else after.strip()


def validate_package(output_dir: Path, deliverable: Path) -> list[str]:
    failures: list[str] = []
    if not deliverable.is_file():
        return [f"missing deliverable: {deliverable}"]
    document = deliverable.read_text(encoding="utf-8")
    for index, title in enumerate(SECTIONS, start=1):
        content = _section_content(document, index, title)
        if not content or "MISSING — fill by codex" in content:
            failures.append(f"section {index} is missing or a template stub")
    owner = output_dir / "reports" / "OWNER_DECISIONS_NEEDED.md"
    if not owner.is_file() or not owner.read_text(encoding="utf-8").strip():
        failures.append("missing non-empty reports/OWNER_DECISIONS_NEEDED.md")
    if not any(path.is_file() and path.stat().st_size for path in (output_dir / "regression").glob("*")):
        failures.append("missing regression evidence")
    patches = [path for path in (output_dir / "commit_diffs").glob("*") if path.is_file()]
    if not patches:
        failures.append("missing commit diff")
    elif not any("diff --git" in path.read_text(encoding="utf-8", errors="replace") for path in patches):
        failures.append("commit diff lacks diff --git marker")
    return failures


def inspect_legacy_package(package: Path) -> str:
    """Read-only historical-package classification; never creates or alters files."""
    if not package.is_dir():
        return "INCOMPATIBLE: package directory missing"
    candidates = [package, *(path for path in package.iterdir() if path.is_dir())]
    for candidate in candidates:
        has_report = (candidate / "reports" / "OWNER_DECISIONS_NEEDED.md").is_file() or (candidate / "OWNER_DECISIONS_NEEDED.md").is_file()
        has_diff = (candidate / "commit_diffs").is_dir() or (candidate / "green_diffs").is_dir()
        has_regression = (candidate / "regression").is_dir()
        if has_report and has_diff and has_regression:
            return "PASS"
    return "NEEDS_ADAPTATION"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--output-dir", required=True, type=Path)
    create.add_argument("--name", required=True)
    create.add_argument("--use-fallback", action="store_true")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--output-dir", required=True, type=Path)
    validate.add_argument("--deliverable", required=True, type=Path)
    inspect = subparsers.add_parser("compat")
    inspect.add_argument("--package", required=True, type=Path)
    hash_command = subparsers.add_parser("sha256")
    hash_command.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "create":
        print(create_package(args.output_dir, args.name, args.use_fallback))
    elif args.command == "validate":
        failures = validate_package(args.output_dir, args.deliverable)
        print("PASS" if not failures else "FAIL: " + "; ".join(failures))
        return 0 if not failures else 1
    elif args.command == "compat":
        print(inspect_legacy_package(args.package))
    else:
        print(sha256(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
