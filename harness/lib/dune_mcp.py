"""dune_mcp.py — Dune 远程 MCP 最小客户端（2026-08-09 建立）。

Dune MCP = Streamable HTTP JSON-RPC 2.0 @ https://api.dune.com/mcp/v1，鉴权 header
`x-dune-api-key`（key 在 config/local_secrets.yaml dune.api_key）。
文档：https://docs.dune.com/docs/agents/mcp

实现最小子集（本项目的链上历史回填用途）：
- initialize / initialized 握手（会话 id 维持）
- tools/list（发现）
- tools/call：searchTables / getUsage / createDuneQuery / executeQueryById /
  getExecutionResults
响应兼容 JSON 与 SSE(text/event-stream) 两种封装。
只读查询创建/执行，不碰可视化/看板。

用法：
    from harness.lib.dune_mcp import DuneMCP
    d = DuneMCP()
    d.initialize()
    print(d.list_tools()[:5])
    qid = d.create_query("my query", "SELECT 1")
    ex = d.execute_query(qid)
    rows = d.get_results(ex)  # list[dict] | None（失败/超时重试由调用方决定）
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRETS = PROJECT_ROOT / "config" / "local_secrets.yaml"

ACCEPT = "application/json, text/event-stream"


class DuneError(RuntimeError):
    pass


class DuneMCP:
    def __init__(self) -> None:
        with SECRETS.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)["dune"]
        self.url = cfg["mcp_url"]
        self.key = cfg["api_key"]
        self.session_id: str | None = None
        self._id = 0

    # ---- 传输层 ----

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": ACCEPT,
            "MCP-Protocol-Version": "2025-03-26",
            "x-dune-api-key": self.key,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=body, headers=headers)
        import http.client
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    self.session_id = r.headers.get("Mcp-Session-Id", self.session_id)
                    raw = r.read().decode("utf-8")
                return self._parse(raw)
            except http.client.IncompleteRead as exc:  # 大响应断连 → 重试
                if attempt == 2:
                    raise
                import time
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError("unreachable")

    @staticmethod
    def _parse(raw: str) -> dict:
        """兼容 JSON 与 SSE 帧（event: message 行 + data: {...} 行）。"""
        lines = raw.splitlines()
        if any(ln.startswith("data:") for ln in lines):
            parts = [ln[5:].strip() for ln in lines if ln.startswith("data:")]
            parsed = [json.loads(p) for p in parts if p]
            return parsed[-1] if parsed else {}
        return json.loads(raw) if raw.strip() else {}

    def _call(self, method: str, params: dict | None = None, _id: int | None = None) -> dict:
        self._id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": _id or self._id, "method": method}
        if params is not None:
            payload["params"] = params
        resp = self._post(payload)
        if "error" in resp:
            raise DuneError(f"Dune {method}: {resp['error']}")
        return resp.get("result", {})

    # ---- MCP 握手 ----

    def initialize(self) -> dict:
        result = self._call("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "alphahive", "version": "1.0"},
        }, _id=1)
        # initialized 通知（无响应）
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except Exception:  # noqa: BLE001
            pass
        return result

    def list_tools(self) -> list[dict]:
        return self._call("tools/list").get("tools", [])

    # ---- 工具封装 ----

    def get_usage(self) -> dict:
        return self._call("tools/call", {"name": "getUsage", "arguments": {}})

    def search_tables(self, query: str, limit: int = 10) -> list[dict]:
        r = self._call("tools/call", {
            "name": "searchTables",
            "arguments": {"query": query, "limit": limit},
        })
        return _text_content(r)

    def create_query(self, name: str, sql: str, description: str = "") -> int:
        r = self._call("tools/call", {
            "name": "createDuneQuery",
            "arguments": {"name": name, "description": description, "query": sql,
                          "is_temp": True},
        })
        return int(_first_text(r))

    def create_and_execute(self, name: str, sql: str, description: str = "",
                           performance: str = "free", max_rows: int = 32000) -> tuple[str, list[dict] | None]:
        """建查询并立即执行。返回 (execution_id, 预览行或 None)。

        Dune 对快查询在同一响应里给 result_preview（state=COMPLETED 时直接含 rows）；
        慢查询需再 getExecutionResults 轮询。
        """
        r = self._call("tools/call", {
            "name": "createAndExecuteQuery",
            "arguments": {"name": name, "description": description, "query": sql,
                          "is_temp": True, "performance": performance,
                          "max_rows_returned": max_rows},
        })
        txt = _first_text(r)
        try:
            obj = json.loads(txt)
            exec_id = obj["execution"]["execution_id"]
            preview = obj.get("result_preview") or {}
            rows = None
            if preview.get("state") == "COMPLETED":
                rows = (preview.get("data") or {}).get("rows")
            return exec_id, rows
        except Exception:  # noqa: BLE001
            raise DuneError(f"createAndExecuteQuery 响应解析失败: {txt[:300]}")

    def run_query(self, name: str, sql: str, max_polls: int = 60,
                  poll_sleep_s: int = 5) -> list[dict] | None:
        """建查询→执行→（如需）轮询到结果。返回 rows 或 None（超时）。"""
        exec_id, rows = self.create_and_execute(name, sql)
        if rows is not None:
            return rows
        return self.get_results(exec_id, max_polls=max_polls, poll_sleep_s=poll_sleep_s)

    def execute_query(self, query_id: int, parameters: dict | None = None) -> str:
        r = self._call("tools/call", {
            "name": "executeQueryById",
            "arguments": {"query_id": query_id, "parameters": parameters or {}},
        })
        return _first_text(r)

    def get_results(self, execution_id: str, max_polls: int = 60, poll_sleep_s: int = 10) -> list[dict] | None:
        """轮询执行结果：COMPLETED → rows；FAILED → DuneError；超时 → None。"""
        import time
        for _ in range(max_polls):
            r = self._call("tools/call", {
                "name": "getExecutionResults",
                "arguments": {"executionId": execution_id},
            })
            text = _text_content(r)
            blob = json.dumps(text, ensure_ascii=False).lower()
            if "completed" in blob:
                rows = _rows_from_text(text)
                return rows
            if "failed" in blob or "error" in blob:
                raise DuneError(f"execution {execution_id}: {text}")
            time.sleep(poll_sleep_s)
        return None


# ---- 响应解析辅助 ----

def _text_content(result: dict) -> list[str]:
    """MCP tools/call 的 content[] 文本抽取。"""
    out: list[str] = []
    for c in result.get("content", []):
        if c.get("type") == "text":
            out.append(c.get("text", ""))
    return out


def _first_text(result: dict) -> str:
    txt = _text_content(result)
    return txt[0] if txt else ""


def _rows_from_text(text: list[str]) -> list[dict] | None:
    """从返回文本里提取表格行（JSON 或 markdown）。"""
    for t in text:
        try:
            obj = json.loads(t)
            return obj.get("rows") or (obj if isinstance(obj, list) else None)
        except Exception:  # noqa: BLE001
            continue
    return None


if __name__ == "__main__":
    d = DuneMCP()
    d.initialize()
    tools = d.list_tools()
    print("tools:", [t["name"] for t in tools])
    print("usage:", d.get_usage())
