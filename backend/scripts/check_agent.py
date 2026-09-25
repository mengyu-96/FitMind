"""Opt-in real-provider smoke check with synthetic input; no personal records."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import READ_TOOLS, SAVE_TOOL, CompatiblePlanner  # noqa: E402
from app.config import Settings  # noqa: E402
from app.domain import DomainError  # noqa: E402


def main():
    planner = CompatiblePlanner(Settings())
    messages = [
        {"role": "system", "content": "这是合成接口测试。请严格调用 apply_changes 创建一个 plan，payload 中包含 title 和一个自定义自由字段。不得创建真实数据。"},
        {"role": "user", "content": "请为测试生成‘轻松活动’计划草案，不预设星期和训练量。"},
    ]
    tools = READ_TOOLS + [SAVE_TOOL]
    try:
        final = None
        apply_count = 0
        for _ in range(6):
            first = planner.complete(messages, tools)
            calls = first.get("tool_calls", [])
            if not calls:
                final = first
                break
            messages.append(first)
            for call in calls:
                name = call["function"]["name"]
                if name == "apply_changes":
                    arguments = json.loads(call["function"]["arguments"])
                    operation = arguments["operations"][0]
                    if operation.get("kind") != "plan" or not isinstance(operation.get("payload"), dict):
                        raise RuntimeError("Expected flexible plan payload")
                    apply_count += 1
                    result = {"operation_id": "synthetic", "objects": [operation]}
                elif name == "discover_capabilities":
                    result = {"available": ["read_context", "apply_changes"], "unavailable": []}
                elif name == "read_context":
                    result = {"objects": [], "limit": 30}
                else:
                    raise RuntimeError("Unexpected tool")
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(result, ensure_ascii=False)})
        if apply_count != 1:
            raise RuntimeError("Expected one plan creation")
        if not final.get("content") or final.get("tool_calls"):
            raise RuntimeError("Expected final text")
        print(json.dumps({"model": Settings().model_name, "tool_call": "passed",
                          "flexible_plan_arguments": "passed", "tool_result_roundtrip": "passed"}))
    except DomainError as exc:
        print(json.dumps({"status": "failed", "code": exc.code}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
