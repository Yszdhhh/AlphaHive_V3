"""Pure local bar-by-bar execution simulator for the Paper sandbox."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .paper_plan_engine import PaperPlanRejected, canonical_json, content_hash


class SimulationRejected(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def load_bars(source: str | Path | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(source, (str, Path)):
        rows = list(source)
    else:
        path = Path(source)
        if not path.exists():
            raise SimulationRejected("bar_source_missing")
        if path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        elif path.suffix.lower() in {".jsonl", ".ndjson"}:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            raise SimulationRejected("unsupported_bar_source")
    result = []
    for row in rows:
        try:
            timestamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError
            values = {key: float(row[key]) for key in ("open", "high", "low", "close")}
        except (KeyError, TypeError, ValueError) as exc:
            raise SimulationRejected("invalid_bar") from exc
        if values["low"] <= 0 or values["high"] < values["low"]:
            raise SimulationRejected("invalid_bar_range")
        result.append({"timestamp": timestamp.astimezone(timezone.utc).isoformat(), **values})
    result.sort(key=lambda item: item["timestamp"])
    if not result or any(a["timestamp"] >= b["timestamp"] for a, b in zip(result, result[1:])):
        raise SimulationRejected("duplicate_or_unsorted_bars")
    return result


def _event(event_type: str, simulation_id: str, sequence: int, **payload: Any) -> dict[str, Any]:
    event = {"event_type": event_type, "simulation_id": simulation_id, "sequence": sequence, **payload}
    event["event_hash"] = hashlib.sha256(canonical_json(event).encode("utf-8")).hexdigest()
    return event


def _append_events(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    fd = None
    try:
        for _ in range(200):
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                time.sleep(0.005)
        if fd is None:
            raise SimulationRejected("ledger_busy")
        os.close(fd)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        known = {json.loads(line).get("event_hash") for line in existing.splitlines() if line.strip()}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for event in events:
                if event["event_hash"] in known:
                    continue
                handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if lock.exists():
            lock.unlink()


def run_simulation(
    plan: dict[str, Any],
    bars: str | Path | Iterable[dict[str, Any]],
    initial_equity: float = 100_000.0,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    if plan.get("schema_version") != "paper_plan_v1" or not plan.get("no_live_order_path"):
        raise SimulationRejected("invalid_or_live_plan")
    stored_plan_hash = plan.get("artifact_hash")
    expected_plan_hash = content_hash({key: value for key, value in plan.items() if key != "artifact_hash"})
    if stored_plan_hash != expected_plan_hash:
        raise SimulationRejected("plan_hash_mismatch")
    if initial_equity <= 0:
        raise SimulationRejected("invalid_equity")
    rows = load_bars(bars)
    bars_hash = content_hash(rows)
    simulation_id = "sim_" + content_hash({"plan": plan.get("artifact_hash"), "bars": bars_hash, "equity": initial_equity})[:32]
    if ledger_path and Path(ledger_path).exists():
        old = [json.loads(line) for line in Path(ledger_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        for event in old:
            if event.get("event_type") == "SIMULATION_COMPLETED" and event.get("simulation_id") == simulation_id:
                return {**event["result"], "idempotent_replay": True}
    direction = 1 if plan.get("direction") == "LONG" else -1 if plan.get("direction") == "SHORT" else 0
    if direction == 0:
        raise SimulationRejected("invalid_direction")
    anchor = datetime.fromisoformat(plan["entry_anchor_timestamp_utc"].replace("Z", "+00:00"))
    entry_index = next((i for i, row in enumerate(rows) if datetime.fromisoformat(row["timestamp"]) >= anchor), None)
    if entry_index is None:
        raise SimulationRejected("missing_entry_bar")
    friction_rate = float(plan.get("friction_bps_roundtrip", 0)) / 10000.0 / 2.0
    entry_base = rows[entry_index]["open"]
    entry_price = entry_base * (1 + direction * friction_rate)
    stop_pct = float(plan["stop_distance_pct"]) / 100.0
    stop_price = entry_price * (1 - direction * stop_pct)
    risk_pct = min(float(plan.get("paper_risk_per_trade_pct", 0)), float(plan.get("max_open_portfolio_risk_pct", 0))) / 100.0
    risk_amount = initial_equity * risk_pct
    risk_per_unit = abs(entry_price - stop_price)
    if risk_amount <= 0 or risk_per_unit <= 0:
        raise SimulationRejected("invalid_risk_model")
    quantity = risk_amount / risk_per_unit
    simulation_end = anchor + timedelta(hours=int(plan["horizon_hours"]))
    events = [_event("SIMULATION_STARTED", simulation_id, 1, plan_id=plan["plan_id"], bars_hash=bars_hash)]
    fills: list[dict[str, Any]] = []
    remaining = quantity
    realized = 0.0
    next_target = 0
    targets = plan["take_profit_targets"]
    entry_event = _event("ENTRY_FILLED", simulation_id, 2, timestamp=rows[entry_index]["timestamp"], price=entry_price, quantity=quantity, direction=plan["direction"])
    events.append(entry_event)
    fills.append({"type": "ENTRY", "timestamp": rows[entry_index]["timestamp"], "price": entry_price, "quantity": quantity})
    sequence = 3
    exit_reason = "TIME_STOP"
    last_timestamp = rows[entry_index]["timestamp"]
    for row in rows[entry_index:]:
        last_timestamp = row["timestamp"]
        if remaining <= 1e-12:
            exit_reason = "TARGETS_COMPLETE"
            break
        if direction == 1:
            stop_hit = row["low"] <= stop_price
        else:
            stop_hit = row["high"] >= stop_price
        if stop_hit:
            base_exit = row["open"] if ((direction == 1 and row["open"] < stop_price) or (direction == -1 and row["open"] > stop_price)) else stop_price
            exit_price = base_exit * (1 - direction * friction_rate)
            pnl = (exit_price - entry_price) * remaining * direction
            realized += pnl
            events.append(_event("STOP_FILLED", simulation_id, sequence, timestamp=row["timestamp"], price=exit_price, quantity=remaining, pnl=pnl))
            fills.append({"type": "STOP", "timestamp": row["timestamp"], "price": exit_price, "quantity": remaining, "pnl": pnl})
            remaining = 0.0
            exit_reason = "STOP"
            break
        while next_target < len(targets):
            target = targets[next_target]
            target_price = entry_price * (1 + direction * stop_pct * float(target["r_multiple"]))
            hit = row["high"] >= target_price if direction == 1 else row["low"] <= target_price
            if not hit:
                break
            weight = float(target["exit_weight_pct"]) / 100.0
            close_qty = min(remaining, quantity * weight)
            exit_price = target_price * (1 - direction * friction_rate)
            pnl = (exit_price - entry_price) * close_qty * direction
            realized += pnl
            events.append(_event("TAKE_PROFIT_FILLED", simulation_id, sequence, timestamp=row["timestamp"], price=exit_price, quantity=close_qty, pnl=pnl, target_index=next_target + 1))
            fills.append({"type": "TAKE_PROFIT", "timestamp": row["timestamp"], "price": exit_price, "quantity": close_qty, "pnl": pnl})
            remaining -= close_qty
            next_target += 1
            sequence += 1
            if next_target == 1:
                stop_price = entry_price * (1 + direction * friction_rate)
        if remaining <= 1e-12:
            exit_reason = "TARGETS_COMPLETE"
            break
        if datetime.fromisoformat(row["timestamp"]) >= simulation_end and remaining > 1e-12:
            exit_price = row["close"] * (1 - direction * friction_rate)
            pnl = (exit_price - entry_price) * remaining * direction
            realized += pnl
            events.append(_event("TIME_EXIT_FILLED", simulation_id, sequence, timestamp=row["timestamp"], price=exit_price, quantity=remaining, pnl=pnl))
            fills.append({"type": "TIME_EXIT", "timestamp": row["timestamp"], "price": exit_price, "quantity": remaining, "pnl": pnl})
            remaining = 0.0
            exit_reason = "TIME_STOP"
            break
        sequence += 1
    result = {
        "schema_version": "offline_paper_simulation_v1",
        "simulation_id": simulation_id,
        "plan_id": plan["plan_id"],
        "bars_hash": bars_hash,
        "initial_equity": initial_equity,
        "realized_pnl": realized,
        "final_equity": initial_equity + realized,
        "exit_reason": exit_reason,
        "fills": fills,
        "events": events,
        "idempotent_replay": False,
    }
    snapshot = dict(result)
    snapshot["events"] = list(events)
    completed = _event("SIMULATION_COMPLETED", simulation_id, len(events) + 1, exit_reason=exit_reason, realized_pnl=realized, result=snapshot)
    events.append(completed)
    result["events"] = events
    if ledger_path:
        _append_events(Path(ledger_path), events)
    return result
