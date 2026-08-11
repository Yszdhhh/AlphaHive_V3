"""Push meaningful AlphaHive shadow-pipeline changes to the Hermes Feishu admin DM.

Structured card format (Feishu card schema 2.0, style from Hermes knowledge_card_cardkit).
Credentials remain in Hermes' .env; this project only imports the existing stdlib-only helper.
Best-effort, deduplicated by content digest. Failure never masks the research task exit code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

TZ_CN = timezone(timedelta(hours=8))  # 展示用北京时间
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
STATE_PATH = REPORTS / "feishu_notify_state.json"
HERMES_SCRIPTS = Path(os.environ.get(
    "HERMES_SCRIPTS", r"C:\Users\10639\AppData\Local\hermes\scripts"))

HEADER_TEMPLATE = {
    "scan": "blue",
    "forward": "indigo",
    "paper": "green",
    "error": "red",
}
HEADER_EMOJI = {
    "scan": "📡",
    "forward": "📊",
    "paper": "💰",
    "error": "⚠️",
}
HEADER_TITLE = {
    "scan": "AlphaHive 前向扫描",
    "forward": "AlphaHive 影子判决",
    "paper": "AlphaHive 虚拟交易结算",
    "error": "AlphaHive 后台任务失败",
}


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="feishu_notify_", suffix=".json", dir=REPORTS)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, STATE_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _digest(*paths: Path) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(str(path).encode())
        try:
            h.update(path.read_bytes())
        except FileNotFoundError:
            h.update(b"<missing>")
    return h.hexdigest()[:20]


def _build_card(kind: str, summary: list[str], details: list[str] | None,
                footer: str) -> dict:
    """统一卡片：header(着色) + 摘要 + 明细 + footer。"""
    elements: list[dict] = []
    if summary:
        elements.append({"tag": "markdown", "content": "\n".join(summary)})
    if details:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": "\n".join(details)})
    if footer:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": f"`{footer}`"})
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text",
                      "content": f"{HEADER_EMOJI[kind]} {HEADER_TITLE[kind]}"},
            "template": HEADER_TEMPLATE[kind],
        },
        "body": {"elements": elements},
    }


def _scan_payload() -> tuple[str, dict | None]:
    path = REPORTS / "contract_monitor_candidates.csv"
    if not path.exists():
        return "", None
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return "", None
    shown = rows[-6:]
    summary = [
        f"**{len(rows)} 个新候选** · {datetime.now(TZ_CN):%m-%d %H:%M 北京时间}",
        "以下为本次扫描输出（可能含历史行）",
    ]
    details = []
    for row in shown:
        details.append(
            f"- **{row.get('symbol', '?')}** {row.get('trigger', '?')} "
            f"{'🟢' if str(row.get('direction', '')).upper() == 'LONG' else '🔴'}Long "
            f"| regime={row.get('regime', '?')} | vix={row.get('vix_status', '?')} "
            f"| gate={'✅' if str(row.get('vix_gate_ok', '')).lower() == 'true' else '❌'}")
    return _digest(path), _build_card("scan", summary, details, str(path))


def _forward_payload() -> tuple[str, dict | None]:
    report = REPORTS / "forward_replay_report.md"
    returns = REPORTS / "forward_replay_returns.csv"
    if not report.exists():
        return "", None
    text = report.read_text(encoding="utf-8", errors="replace")
    meaningful = any(token in text for token in ("GO_LONG", "GO_SHORT", "衰退预警"))
    if not meaningful:
        return "", None
    verdict = next((ln.strip() for ln in text.splitlines()
                    if "verdict" in ln.lower()), "")
    warns = [ln.strip() for ln in text.splitlines() if "衰退预警" in ln or "CUSUM" in ln]
    summary = [
        f"**{verdict or '判决更新'}** · {datetime.now(TZ_CN):%m-%d %H:%M 北京时间}",
    ]
    details = warns[-4:] or ["无预警（仅状态变化）"]
    return _digest(report, returns), _build_card("forward", summary, details, str(report))


def _paper_payload() -> tuple[str, dict | None]:
    report = REPORTS / "paper_trade_report.md"
    positions = REPORTS / "paper_positions.csv"
    if not report.exists():
        return "", None
    text = report.read_text(encoding="utf-8", errors="replace")
    if "## 账户" not in text:
        return "", None
    summary: list[str] = [f"{datetime.now(TZ_CN):%m-%d %H:%M 北京时间}"]
    details: list[str] = []
    for line in text.splitlines():
        if re.match(r"^## 账户 [ABCD]$", line) or line == "## 当前持仓":
            details.append(f"\n{line}")
        elif line.startswith("- 已结算") or line.startswith("- 胜率") \
                or line.startswith("- 退出分布") or line.startswith("- 净盈亏") \
                or line.startswith("- 期末净值") or line.startswith("- 最大回撤") \
                or line.startswith("- **数据性质") \
                or (line.startswith("- ") and "持仓中" in line):
            details.append(line.replace("- ", "  · "))
    # D 账户收益摘要置顶（主收益池）
    d_idx = next((i for i, ln in enumerate(details) if ln == "\n## 账户 D"), -1)
    if d_idx >= 0:
        for ln in details[d_idx:d_idx + 4]:
            m = re.search(r"净盈亏 \$([+-]?[\d,.]+)；期末净值 \$([\d,.]+)", ln)
            if m:
                summary.append(f"D 账户：净盈亏 **${m.group(1)}** · 净值 **${m.group(2)}**")
                break
    # 当前持仓概览（按账户计数）
    seg = text.split("## 当前持仓")[1].split("##")[0] if "## 当前持仓" in text else ""
    by_acct: dict[str, int] = {}
    pend_rows: list[tuple[float, list[str]]] = []
    for line in seg.splitlines():
        if line.startswith("|") and not line.startswith("| 账户") and not line.startswith("|---"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 6:
                continue
            if parts[0] in "ABCD":
                by_acct[parts[0]] = by_acct.get(parts[0], 0) + 1
            if parts[0] in "ABCD" and parts[4] != "-":
                try:
                    fl = float(parts[4].rstrip("%"))
                except ValueError:
                    fl = float("inf")
                pend_rows.append((fl, parts))
    if by_acct:
        summary.append("当前持仓 " + " · ".join(f"{k} {v}笔" for k, v in sorted(by_acct.items())))
        if pend_rows:
            details.append("\n## 当前持仓（最差浮盈 5 笔）")
            for fl, parts in sorted(pend_rows)[:5]:
                batch = parts[6] if len(parts) > 6 and parts[6] else ""
                details.append(f"  · {parts[0]} {parts[1]}：浮盈 {parts[4]}（{parts[5]}h{batch}）")
    # 单币盈亏 Top5（D 账户）
    seg2 = text.split("## 账户 D 单币盈亏")[1].split("##")[0] if "## 账户 D 单币盈亏" in text else ""
    top_rows = [ln for ln in seg2.splitlines()
                if ln.startswith("|") and not ln.startswith("| symbol") and not ln.startswith("|---")
                and "其余" not in ln][:5]
    if top_rows:
        details.append("\n## 单币盈亏 Top（D）")
        for ln in top_rows:
            parts = [p.strip() for p in ln.strip("|").split("|")]
            details.append(f"  · {parts[0]}：{parts[2]}（{parts[1]}笔，胜率{parts[3]}）")
    return _digest(report, positions), _build_card("paper", summary, details, str(report))


def _error_payload(kind: str, exit_code: int, stderr: str) -> tuple[str, dict]:
    """简洁清晰版错误卡片：一句话原因 + 位置，不再裸贴 traceback。"""
    lines = [ln.rstrip() for ln in stderr.splitlines() if ln.strip()]
    err_pat = re.compile(
        r"^(KeyError|ValueError|TypeError|IndexError|FileNotFoundError|AttributeError|"
        r"RuntimeError|OSError|Exception|AssertionError|NameError|ModuleNotFoundError|"
        r"ImportError|MemoryError|OverflowError|RecursionError|pandas\.errors\.\w+)\b")
    err_line = next((ln for ln in reversed(lines) if err_pat.match(ln)), "")
    cause = err_line.split(":", 1)[1].strip() if ":" in err_line else err_line
    file_lines = [ln.strip() for ln in reversed(lines) if ln.strip().startswith("File ")]
    loc = next((ln for ln in file_lines if "AlphaHive_V3" in ln or "scripts\\" in ln), file_lines[0] if file_lines else "")
    summary = [
        f"任务 **{kind}** 执行失败 · 退出码 **{exit_code}**",
        f"{datetime.now(TZ_CN):%m-%d %H:%M 北京时间}",
    ]
    details: list[str] = []
    if cause:
        details.append(f"**原因**：`{cause[:200]}`")
    if loc:
        details.append(f"**位置**：`{loc[:180]}`")
    if not details:
        details = [f"```\n{stderr[-500:]}\n```"] if stderr.strip() else ["无 stderr"]
    key = f"error:{kind}:{exit_code}:{hashlib.sha256(stderr.encode()).hexdigest()[:12]}"
    return key, _build_card("error", summary, details, "")


def _recipient_open_id() -> str:
    """Use explicit admin id, then Hermes' allowed-user id; never guess a default."""
    if os.environ.get("FEISHU_ADMIN_OPEN_ID"):
        return os.environ["FEISHU_ADMIN_OPEN_ID"]
    env_path = HERMES_SCRIPTS.parent / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("FEISHU_ALLOWED_USERS="):
                return line.split("=", 1)[1].strip().split(",", 1)[0].strip()
    except FileNotFoundError:
        pass
    return ""


# 系统运行情况推送目标：quant 群聊（2026-08-11 Owner 指定）；环境变量 FEISHU_CHAT_ID 可覆盖
DEFAULT_CHAT_ID = "oc_b09f882231082604d0796e5af1c7c266"


def _send(card: dict, state: dict, kind: str) -> bool:
    """优先发 quant 群，失败回退管理员 DM。返回是否成功。"""
    sys.path.insert(0, str(HERMES_SCRIPTS))
    try:
        from feishu_dm_notify import send_card, send_card_to_chat
    except Exception as exc:
        print(f"[notify] Hermes helper unavailable: {exc}", file=sys.stderr)
        return False
    chat_id = os.environ.get("FEISHU_CHAT_ID") or DEFAULT_CHAT_ID
    if chat_id and send_card_to_chat(card, chat_id):
        return True
    recipient = _recipient_open_id()
    if recipient and send_card(card, recipient):
        print("[notify] chat send failed, fell back to admin DM", file=sys.stderr)
        return True
    print("[notify] no Feishu recipient reachable", file=sys.stderr)
    return False


def notify(kind: str, *, exit_code: int = 0, stderr: str = "", dry_run: bool = False) -> bool:
    state = _load_state()
    if exit_code:
        key, card = _error_payload(kind, exit_code, stderr)
    elif kind == "scan":
        key, card = _scan_payload()
    elif kind == "forward":
        key, card = _forward_payload()
    elif kind == "paper":
        key, card = _paper_payload()
    else:
        raise ValueError(f"unknown notification kind: {kind}")
    if not key or card is None:
        print(f"[notify] {kind}: no meaningful change")
        return True
    if state.get(kind) == key:
        print(f"[notify] {kind}: duplicate suppressed")
        return True
    if dry_run:
        print(json.dumps(card, ensure_ascii=False, indent=1))
        return True
    ok = _send(card, state, kind)
    if ok:
        state[kind] = key
        _save_state(state)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["scan", "forward", "paper"])
    ap.add_argument("--exit-code", type=int, default=0)
    ap.add_argument("--stderr", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return 0 if notify(args.kind, exit_code=args.exit_code,
                       stderr=args.stderr, dry_run=args.dry_run) else 1


if __name__ == "__main__":
    raise SystemExit(main())
