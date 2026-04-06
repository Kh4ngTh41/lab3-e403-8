"""
AI Research & Decision Assistant — Main Entry Point
=====================================================
Interactive CLI for the ReAct crypto agent.

Usage:
    python -m src.main
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from src.tools.registry import build_default_registry
from src.agent.agent import ReActAgent
from src.telemetry.logger import logger


def _create_llm_provider():
    """Factory: create the LLM provider based on .env config."""
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            print("[WARNING] OPENAI_API_KEY chua duoc cau hinh trong .env")
            sys.exit(1)
        return OpenAIProvider(model_name=model_name, api_key=api_key)

    elif provider_name == "google":
        from src.core.gemini_provider import GeminiProvider
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            print("[WARNING] GEMINI_API_KEY chua duoc cau hinh trong .env")
            sys.exit(1)
        return GeminiProvider(model_name=model_name, api_key=api_key)

    elif provider_name == "local":
        from src.core.local_provider import LocalProvider
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=model_path)

    else:
        print(f"[ERROR] Provider '{provider_name}' khong ho tro. Dung: openai | google | local")
        sys.exit(1)


def main():
    print("=" * 60)
    print("AI Research & Decision Assistant")
    print("   Chuyên gia phân tích Crypto — Powered by ReAct Agent")
    print("=" * 60)
    print()
    print("Gợi ý câu hỏi:")
    print("  • Giá Bitcoin hiện tại là bao nhiêu?")
    print("  • Giá BTC tăng bao nhiêu % trong 7 ngày?")
    print("  • Có tin tức gì gần đây về Bitcoin?")
    print("  • Tóm tắt tình hình Bitcoin hiện tại")
    print("  • Tôi có nên mua Bitcoin lúc này không?")
    print()
    print("Gõ 'exit' hoặc 'quit' để thoát.\n")

    # ── Initialize ──
    llm = _create_llm_provider()
    registry = build_default_registry()
    agent = ReActAgent(llm=llm, registry=registry, max_steps=5)

    logger.log_event("APP_START", {"provider": os.getenv("DEFAULT_PROVIDER")})

    # ── Interactive Loop ──
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTam biet!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Tam biet!")
            break

        print("\nDang xu ly...\n")
        response = agent.run(user_input)
        print(f"Agent: {response}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()
