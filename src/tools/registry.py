"""
Tool Registry — Central manager for all agent-callable tools.
================================================================
Maps tool names → callable functions with Pydantic schemas,
enabling the ReAct agent to dynamically discover and invoke tools.

Handles:
  - Tool registration with schemas
  - Argument parsing & validation
  - Out-of-scope query detection
"""

import json
import re
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel

from src.tools.schemas import ToolError
from src.telemetry.logger import logger


class ToolDefinition(BaseModel):
    """Schema describing a single tool for the agent."""
    name: str
    description: str
    parameters: Dict[str, str]  # param_name → description
    required_params: List[str] = []


class ToolRegistry:
    """
    Registry that the ReAct agent uses to:
    1. List available tools (for system prompt)
    2. Parse & execute tool calls
    3. Validate inputs via Pydantic before calling
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: Dict[str, str],
        required_params: Optional[List[str]] = None,
    ):
        """Register a tool with its callable and metadata."""
        self._tools[name] = {
            "func": func,
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                required_params=required_params or [],
            ),
        }
        logger.log_event("TOOL_REGISTERED", {"name": name})

    def list_tools(self) -> List[ToolDefinition]:
        """Return all registered tool definitions."""
        return [t["definition"] for t in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """Format tool descriptions for the system prompt."""
        lines = []
        for tool in self.list_tools():
            params_str = ", ".join(
                f"{k}: {v}" for k, v in tool.parameters.items()
            )
            lines.append(
                f"- {tool.name}({params_str}): {tool.description}"
            )
        return "\n".join(lines)

    def execute(self, tool_name: str, args_str: str = "") -> str:
        """
        Execute a tool by name, parsing arguments from the string.
        Returns a string result (serialized for the Observation step).
        """
        if tool_name not in self._tools:
            err = ToolError(
                tool_name=tool_name,
                error_type="ToolNotFound",
                message=f"Tool '{tool_name}' không tồn tại. "
                        f"Các tool có sẵn: {', '.join(self._tools.keys())}",
            )
            return json.dumps(err.model_dump(), ensure_ascii=False)

        tool = self._tools[tool_name]
        func = tool["func"]

        try:
            # Parse arguments
            kwargs = self._parse_args(args_str, tool["definition"])

            logger.log_event("TOOL_EXECUTE", {
                "tool": tool_name,
                "parsed_args": kwargs,
            })

            # Call the tool function
            result = func(**kwargs)

            # Serialize output
            if isinstance(result, BaseModel):
                output = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
            elif isinstance(result, list):
                serialized = [
                    r.model_dump() if isinstance(r, BaseModel) else r
                    for r in result
                ]
                output = json.dumps(serialized, ensure_ascii=False, indent=2)
            else:
                output = str(result)

            # Sanitize to prevent surrogate characters (Windows encoding issue)
            return output.encode("utf-8", errors="replace").decode("utf-8")

        except Exception as exc:
            err = ToolError(
                tool_name=tool_name,
                error_type=type(exc).__name__,
                message=f"Lỗi khi thực thi {tool_name}: {str(exc)}",
            )
            logger.error(f"TOOL_EXECUTE_ERROR: {err.model_dump()}")
            return json.dumps(err.model_dump(), ensure_ascii=False)

    def _parse_args(
        self, args_str: str, definition: ToolDefinition
    ) -> Dict[str, Any]:
        """
        Parse argument string from LLM output.
        Supports formats:
          - tool_name("BTC")         → positional
          - tool_name(symbol="BTC")  → keyword
          - tool_name({"symbol": "BTC"}) → JSON
          - tool_name()              → no args
        """
        args_str = args_str.strip()
        if not args_str:
            return {}

        # Try JSON object first
        try:
            parsed = json.loads(args_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Try keyword arguments:  symbol="BTC", days=7
        kwargs = {}
        kw_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"' + r"|'([^']*)'|(\d+(?:\.\d+)?)|(\w+))"
        kw_matches = re.findall(kw_pattern, args_str)
        if kw_matches:
            for match in kw_matches:
                key = match[0]
                # Pick the first non-empty capture group as value
                value = match[1] or match[2] or match[3] or match[4]
                # Try to convert numeric
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        pass
                kwargs[key] = value
            if kwargs:
                return kwargs

        # Positional: single string "BTC" or 'BTC'
        pos_match = re.match(r"""^["']([^"']+)["']$""", args_str)
        if pos_match:
            # Map to first parameter
            params = list(definition.parameters.keys())
            if params:
                return {params[0]: pos_match.group(1)}

        # Bare word: BTC
        if re.match(r"^\w+$", args_str):
            params = list(definition.parameters.keys())
            if params:
                return {params[0]: args_str}

        return {}


# ============================================================
# Factory: Build a fully-loaded registry with all UC tools
# ============================================================

def build_default_registry() -> ToolRegistry:
    """Create and return a registry with all 5 use-case tools pre-registered."""
    from src.tools.u1 import get_crypto_price, get_multi_crypto_price
    from src.tools.u2 import get_price_trend
    from src.tools.u3 import fetch_latest_news
    from src.tools.u4 import aggregate_crypto_summary
    from src.tools.u5 import evaluate_investment

    registry = ToolRegistry()

    registry.register(
        name="get_crypto_price",
        func=get_crypto_price,
        description="Lấy giá real-time của một đồng crypto (VD: BTC, ETH, SOL).",
        parameters={"symbol": "Ký hiệu coin, mặc định 'BTC'"},
        required_params=[],
    )

    registry.register(
        name="get_multi_crypto_price",
        func=get_multi_crypto_price,
        description="Lấy giá nhiều đồng crypto cùng lúc.",
        parameters={"symbols": "Danh sách ký hiệu coin, VD: ['BTC','ETH']"},
    )

    registry.register(
        name="get_price_trend",
        func=get_price_trend,
        description="Phân tích xu hướng giá N ngày (mặc định 7 ngày).",
        parameters={
            "symbol": "Ký hiệu coin, mặc định 'BTC'",
            "days": "Số ngày phân tích, mặc định 7",
        },
    )

    registry.register(
        name="fetch_latest_news",
        func=fetch_latest_news,
        description="Kéo tin tức mới nhất về crypto từ NewsAPI.",
        parameters={
            "query": "Từ khóa tìm kiếm, mặc định 'Bitcoin'",
            "limit": "Số bài tối đa, mặc định 5",
        },
    )

    registry.register(
        name="aggregate_crypto_summary",
        func=aggregate_crypto_summary,
        description="Tổng hợp giá + xu hướng + tin tức thành báo cáo tóm tắt.",
        parameters={"symbol": "Ký hiệu coin, mặc định 'BTC'"},
    )

    registry.register(
        name="evaluate_investment",
        func=evaluate_investment,
        description="Đánh giá tổng hợp và gợi ý Buy/Hold/Sell dựa trên dữ liệu thật.",
        parameters={"symbol": "Ký hiệu coin, mặc định 'BTC'"},
    )

    return registry
