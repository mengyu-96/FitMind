"""Opt-in real-provider smoke check with synthetic input; no personal records."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import CompatiblePlanner, tool  # noqa: E402
from app.config import Settings  # noqa: E402
from app.domain import DomainError  # noqa: E402


def main():
    planner = CompatiblePlanner(Settings())
    messages = [
        {"role": "system", "content": "这是接口测试。先调用 ping 工具，再回复测试完成。"},
        {"role": "user", "content": "请开始合成数据测试，不涉及真实个人信息。"},
    ]
    tools = [tool("ping", "验证工具调用链路。", {})]
    try:
        first = planner.complete(messages, tools)
        calls = first.get("tool_calls", [])
        if not calls or any(c["function"]["name"] != "ping" for c in calls):
            raise RuntimeError("Expected ping tool call")
        messages.append(first)
        messages.extend({"role": "tool", "tool_call_id": c["id"], "content": '{"ok":true}'} for c in calls)
        final = planner.complete(messages, tools)
        if not final.get("content") or final.get("tool_calls"):
            raise RuntimeError("Expected final text")
        print(json.dumps({"model": Settings().model_name, "tool_call": "passed",
                          "tool_result_roundtrip": "passed"}))
    except DomainError as exc:
        print(json.dumps({"status": "failed", "code": exc.code}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
