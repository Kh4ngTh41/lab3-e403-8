"""
ReAct Agent — Thought → Action → Observation loop
===================================================
Implements a complete ReAct cycle with:
  - Dynamic tool execution via ToolRegistry
  - Out-of-scope query guardrails
  - Structured error handling
  - Telemetry integration
"""

import re
import json
from typing import Optional

from src.core.llm_provider import LLMProvider
from src.tools.registry import ToolRegistry, build_default_registry
from src.telemetry.logger import logger


# ── Keywords/topics that define the agent's scope ────────────
SCOPE_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "coin",
    "solana", "sol", "bnb", "xrp", "ada", "doge", "dot",
    "avax", "matic", "link", "uni", "atom",
    "giá", "price", "trend", "xu hướng", "tin tức", "news",
    "mua", "bán", "buy", "sell", "hold", "đầu tư", "invest",
    "tóm tắt", "summary", "phân tích", "analysis", "analyze",
    "market", "thị trường", "portfolio", "danh mục",
]


class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought → Action → Observation loop.
    Equipped with a ToolRegistry for dynamic tool management.
    """

    def __init__(
        self,
        llm: LLMProvider,
        registry: Optional[ToolRegistry] = None,
        max_steps: int = 8,
    ):
        self.llm = llm
        self.registry = registry or build_default_registry()
        self.max_steps = max_steps
        self.history = []

    # ── Scope Guard ──────────────────────────────────────────

    def _is_in_scope(self, user_input: str) -> bool:
        """
        Check if the user's question is within the agent's domain.
        Returns False for out-of-scope queries (e.g. "thời tiết hôm nay").
        """
        text = user_input.lower()
        return any(kw in text for kw in SCOPE_KEYWORDS)

    def _out_of_scope_response(self, user_input: str) -> str:
        """Polite rejection for off-topic queries."""
        return (
            "Xin loi, toi la AI Research & Decision Assistant chuyen ve Crypto.\n"
            "Toi co the giup ban voi:\n"
            "  - Gia crypto real-time (BTC, ETH, SOL, ...)\n"
            "  - Phan tich xu huong gia\n"
            "  - Tin tuc crypto moi nhat\n"
            "  - Tom tat tinh hinh thi truong\n"
            "  - Goi y Buy/Hold/Sell dua tren du lieu\n\n"
            f'Cau hoi cua ban ("{user_input}") nam ngoai pham vi cua toi. '
            "Vui long hoi ve crypto!"
        )

    # ── System Prompt ────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """
        Build the system prompt with available tools and ReAct format instructions.
        """
        tool_desc = self.registry.get_tool_descriptions()
        return (
            "You are an AI Research & Decision Assistant specialized in cryptocurrency analysis.\n"
            "You have access to the following tools:\n"
            f"{tool_desc}\n\n"
            "You MUST follow this EXACT format for EVERY step:\n\n"
            "Thought: <your reasoning about what to do next>\n"
            "Action: <tool_name>(<arguments>)\n\n"
            "After I give you the Observation (tool result), continue with another Thought/Action, "
            "or provide your final answer:\n\n"
            "Thought: I now have enough information to answer.\n"
            "Final Answer: <your comprehensive answer to the user>\n\n"
            "STRATEGY FOR COMPREHENSIVE QUERIES:\n"
            "When the user asks for full analysis, investment advice, or wants to understand "
            "the overall situation of a coin, you MUST gather data from MULTIPLE tools before "
            "giving a Final Answer. Follow this sequence:\n"
            "  1. get_crypto_price(symbol) -- get current price and 24h change\n"
            "  2. get_price_trend(symbol, days) -- get trend over the requested period\n"
            "  3. fetch_latest_news(query) -- get recent news and events\n"
            "  4. evaluate_investment(symbol) -- get Buy/Hold/Sell recommendation\n"
            "Do NOT skip any step. Do NOT give a Final Answer until you have called "
            "at least get_crypto_price, get_price_trend, AND fetch_latest_news.\n\n"
            "RULES:\n"
            "- ALWAYS start with a Thought.\n"
            "- Call ONE tool per Action step.\n"
            "- Arguments can be: tool(\"value\") or tool(param=\"value\", param2=123)\n"
            "- If a tool returns an error, think about whether to retry or use alternative data.\n"
            "- Final Answer should be in the SAME LANGUAGE as the user's question.\n"
            "- Include relevant numbers, percentages, and data in your Final Answer.\n"
            "- ALWAYS include news/events analysis in your Final Answer when available.\n"
            "- Add disclaimers for investment-related advice.\n"
        )

    # ── ReAct Loop ───────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """
        Execute the full ReAct loop:
        1. Check scope
        2. Generate Thought + Action via LLM
        3. Parse Action → execute tool → get Observation
        4. Repeat until Final Answer or max_steps
        """
        logger.log_event("AGENT_START", {
            "input": user_input,
            "model": self.llm.model_name,
        })

        # ── Scope Guard ──
        if not self._is_in_scope(user_input):
            response = self._out_of_scope_response(user_input)
            logger.log_event("AGENT_OUT_OF_SCOPE", {"input": user_input})
            return response

        # ── Build conversation context ──
        conversation = f"User question: {user_input}\n\n"
        steps = 0

        while steps < self.max_steps:
            steps += 1
            logger.log_event("AGENT_STEP", {"step": steps})

            # ── Generate LLM response ──
            try:
                # Sanitize to remove surrogate characters (Windows encoding issue)
                safe_conversation = conversation.encode("utf-8", errors="replace").decode("utf-8")
                result = self.llm.generate(
                    prompt=safe_conversation,
                    system_prompt=self.get_system_prompt(),
                )
                llm_output = result["content"]
            except Exception as exc:
                logger.error(f"LLM_ERROR at step {steps}: {exc}")
                return f"[ERROR] Loi khi goi LLM: {str(exc)}"

            logger.log_event("LLM_RESPONSE", {
                "step": steps,
                "content_preview": llm_output[:300],
                "usage": result.get("usage", {}),
            })

            # ── Check for Final Answer ──
            final_answer = self._extract_final_answer(llm_output)
            if final_answer:
                self.history.append({
                    "input": user_input,
                    "output": final_answer,
                    "steps": steps,
                })
                logger.log_event("AGENT_END", {
                    "steps": steps,
                    "has_answer": True,
                })
                return final_answer

            # ── Parse Action ──
            action = self._extract_action(llm_output)
            if not action:
                # LLM didn't follow format — append guidance and retry
                conversation += (
                    f"{llm_output}\n\n"
                    "Observation: You must use the format 'Action: tool_name(args)' "
                    "or provide a 'Final Answer:'. Please try again.\n\n"
                )
                continue

            tool_name, args_str = action

            # ── Execute tool ──
            observation = self.registry.execute(tool_name, args_str)

            # ── Append to conversation ──
            conversation += (
                f"{llm_output}\n"
                f"Observation: {observation}\n\n"
            )

            logger.log_event("TOOL_OBSERVATION", {
                "step": steps,
                "tool": tool_name,
                "observation_preview": observation[:300],
            })

        # ── Max steps reached ──
        logger.log_event("AGENT_END", {"steps": steps, "has_answer": False})
        return (
            "[WARNING] Da dat gioi han buoc xu ly. "
            "Toi khong the hoan thanh phan tich. Vui long thu lai voi cau hoi cu the hon."
        )

    # ── Traced run (for Streamlit UI) ────────────────────────

    def run_with_trace(self, user_input: str):
        """
        Same ReAct loop as run(), but yields structured step dicts
        so the UI can display Thought/Action/Observation live.

        Yields dicts with keys:
          - type: "scope_reject" | "thought" | "action" | "observation" |
                  "final_answer" | "error" | "max_steps"
          - step: int
          - content: str
          - (optional) tool, args, usage, latency_ms
        """
        import time

        logger.log_event("AGENT_START", {
            "input": user_input,
            "model": self.llm.model_name,
        })

        # ── Scope Guard ──
        if not self._is_in_scope(user_input):
            response = self._out_of_scope_response(user_input)
            logger.log_event("AGENT_OUT_OF_SCOPE", {"input": user_input})
            yield {"type": "scope_reject", "step": 0, "content": response}
            return

        conversation = f"User question: {user_input}\n\n"
        steps = 0

        while steps < self.max_steps:
            steps += 1
            logger.log_event("AGENT_STEP", {"step": steps})

            # ── Generate LLM response ──
            try:
                safe_conversation = conversation.encode("utf-8", errors="replace").decode("utf-8")
                t0 = time.time()
                result = self.llm.generate(
                    prompt=safe_conversation,
                    system_prompt=self.get_system_prompt(),
                )
                latency = int((time.time() - t0) * 1000)
                llm_output = result["content"]
            except Exception as exc:
                logger.error(f"LLM_ERROR at step {steps}: {exc}")
                yield {
                    "type": "error",
                    "step": steps,
                    "content": f"[ERROR] Loi khi goi LLM: {str(exc)}",
                }
                return

            usage = result.get("usage", {})

            # ── Extract Thought ──
            thought = self._extract_thought(llm_output)
            if thought:
                yield {
                    "type": "thought",
                    "step": steps,
                    "content": thought,
                    "usage": usage,
                    "latency_ms": latency,
                }

            # ── Check for Final Answer ──
            final_answer = self._extract_final_answer(llm_output)
            if final_answer:
                self.history.append({
                    "input": user_input,
                    "output": final_answer,
                    "steps": steps,
                })
                logger.log_event("AGENT_END", {"steps": steps, "has_answer": True})
                yield {
                    "type": "final_answer",
                    "step": steps,
                    "content": final_answer,
                }
                return

            # ── Parse Action ──
            action = self._extract_action(llm_output)
            if not action:
                conversation += (
                    f"{llm_output}\n\n"
                    "Observation: You must use the format 'Action: tool_name(args)' "
                    "or provide a 'Final Answer:'. Please try again.\n\n"
                )
                yield {
                    "type": "warning",
                    "step": steps,
                    "content": "LLM không follow đúng format, đang retry...",
                    "raw_output": llm_output,
                }
                continue

            tool_name, args_str = action

            yield {
                "type": "action",
                "step": steps,
                "content": f"{tool_name}({args_str})",
                "tool": tool_name,
                "args": args_str,
            }

            # ── Execute tool ──
            t0 = time.time()
            observation = self.registry.execute(tool_name, args_str)
            tool_latency = int((time.time() - t0) * 1000)

            conversation += (
                f"{llm_output}\n"
                f"Observation: {observation}\n\n"
            )

            logger.log_event("TOOL_OBSERVATION", {
                "step": steps,
                "tool": tool_name,
                "observation_preview": observation[:300],
            })

            yield {
                "type": "observation",
                "step": steps,
                "content": observation,
                "tool": tool_name,
                "latency_ms": tool_latency,
            }

        # ── Max steps ──
        logger.log_event("AGENT_END", {"steps": steps, "has_answer": False})
        yield {
            "type": "max_steps",
            "step": steps,
            "content": (
                "[WARNING] Da dat gioi han buoc xu ly. "
                "Vui long thu lai voi cau hoi cu the hon."
            ),
        }

    # ── Parsing Helpers ──────────────────────────────────────

    def _extract_thought(self, text: str) -> Optional[str]:
        """Extract 'Thought: ...' from LLM output (up to Action or Final Answer)."""
        match = re.search(
            r"Thought:\s*(.+?)(?=\n\s*(?:Action:|Final Answer:)|$)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    def _extract_final_answer(self, text: str) -> Optional[str]:
        """Extract 'Final Answer: ...' from LLM output."""
        match = re.search(
            r"Final Answer:\s*(.+)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    def _extract_action(self, text: str):
        """
        Extract 'Action: tool_name(args)' from LLM output.
        Returns (tool_name, args_str) or None.
        """
        # Pattern: Action: tool_name(...)
        match = re.search(
            r"Action:\s*(\w+)\(([^)]*)\)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1), match.group(2)

        # Fallback: Action: tool_name
        match = re.search(
            r"Action:\s*(\w+)\s*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if match:
            return match.group(1), ""

        return None
