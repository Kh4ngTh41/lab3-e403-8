"""
Streamlit UI for ReAct Crypto Agent
======================================
Shows the agent's Thought -> Action -> Observation loop
with a clean, sanitized log display.

Run:  streamlit run app.py
"""

import os
import sys
import json
import streamlit as st
from dotenv import load_dotenv

# -- Load env before anything else --
load_dotenv()

# -- Ensure project root is on the path --
sys.path.insert(0, os.path.dirname(__file__))

from src.tools.registry import build_default_registry
from src.agent.agent import ReActAgent


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def _sanitize(text: str) -> str:
    """Remove surrogate chars that break rendering."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _create_llm():
    """Factory matching main.py but without sys.exit."""
    provider = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    model = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(model_name=model, api_key=os.getenv("OPENAI_API_KEY"))
    elif provider == "google":
        from src.core.gemini_provider import GeminiProvider
        return GeminiProvider(model_name=model, api_key=os.getenv("GEMINI_API_KEY"))
    elif provider == "local":
        from src.core.local_provider import LocalProvider
        return LocalProvider(model_path=os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf"))
    else:
        st.error(f"Provider '{provider}' khong duoc ho tro.")
        st.stop()


def _pretty_json(raw: str) -> str:
    """Try to pretty-print JSON, fall back to raw."""
    try:
        obj = json.loads(raw)
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return raw


# -- Step-type -> color mapping --

STEP_CONFIG = {
    "thought":      {"label": "THINKING",      "color": "#7c3aed"},
    "action":       {"label": "ACTION",         "color": "#2563eb"},
    "observation":  {"label": "OBSERVATION",    "color": "#059669"},
    "final_answer": {"label": "FINAL ANSWER",   "color": "#16a34a"},
    "error":        {"label": "ERROR",           "color": "#dc2626"},
    "warning":      {"label": "WARNING",         "color": "#d97706"},
    "scope_reject": {"label": "OUT OF SCOPE",   "color": "#6b7280"},
    "max_steps":    {"label": "MAX STEPS",       "color": "#d97706"},
}


# -------------------------------------------------------------
# Page Config
# -------------------------------------------------------------

st.set_page_config(
    page_title="Crypto ReAct Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------
# Custom CSS
# -------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.main .block-container {
    max-width: 1100px;
    padding-top: 2rem;
}

.app-header {
    text-align: center;
    padding: 1.5rem 0 1rem;
}
.app-header h1 {
    font-family: 'Inter', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #7c3aed 0%, #2563eb 50%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.25rem;
}
.app-header p {
    color: #9ca3af;
    font-size: 0.95rem;
}

.step-card {
    border-left: 4px solid var(--accent);
    background: rgba(255,255,255,0.03);
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    margin-bottom: 0.6rem;
    font-family: 'Inter', sans-serif;
}
.step-card .step-header {
    font-weight: 600;
    font-size: 0.85rem;
    margin-bottom: 0.35rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------

with st.sidebar:
    st.markdown("### Cau hinh")
    provider = os.getenv("DEFAULT_PROVIDER", "openai")
    model = os.getenv("DEFAULT_MODEL", "gpt-4o")
    st.markdown(f"**Provider:** `{provider}`")
    st.markdown(f"**Model:** `{model}`")
    st.divider()

    max_steps = st.slider("Max ReAct steps", 1, 15, 8)
    show_raw_obs = st.checkbox("Hien raw JSON (Observation)", value=False)
    st.divider()

    st.markdown("### Cach doc log")
    st.markdown("""
    | Label | Y nghia |
    |-------|---------|
    | THINKING | Agent suy luan |
    | ACTION | Goi tool |
    | OBSERVATION | Ket qua tool |
    | FINAL ANSWER | Tra loi |
    | ERROR | Loi |
    | OUT OF SCOPE | Ngoai pham vi |
    """)

    st.divider()
    if st.button("Xoa lich su", use_container_width=True):
        st.session_state.messages = []
        st.session_state.traces = []
        st.rerun()


# -------------------------------------------------------------
# Session State
# -------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "traces" not in st.session_state:
    st.session_state.traces = []
if "agent" not in st.session_state:
    llm = _create_llm()
    registry = build_default_registry()
    st.session_state.agent = ReActAgent(llm=llm, registry=registry, max_steps=8)


# -------------------------------------------------------------
# Header
# -------------------------------------------------------------

st.markdown("""
<div class="app-header">
    <h1>Crypto ReAct Agent</h1>
    <p>Phan tich Crypto voi ReAct -- Xem agent suy luan tung buoc</p>
</div>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# Render past messages
# -------------------------------------------------------------

def _format_observation(obj: dict) -> str:
    """Format a tool observation dict into a readable string."""
    lines = []

    # -- Error response --
    if "error_type" in obj:
        lines.append(f"**Error:** {obj.get('error_type')} -- {obj.get('message', '')}")
        return "\n".join(lines)

    # -- News response (has 'articles' key) --
    if "articles" in obj and isinstance(obj["articles"], list):
        query = obj.get("query", "")
        total = obj.get("total_results", len(obj["articles"]))
        lines.append(f"**Query:** {query} | **Results:** {total}")
        lines.append("")
        for i, art in enumerate(obj["articles"], 1):
            title = art.get("title", "N/A")
            desc = art.get("description", "")
            url = art.get("url", "")
            pub = art.get("published_at", "")
            lines.append(f"**{i}. {title}**")
            if desc:
                lines.append(f"   {desc[:200]}")
            if pub:
                lines.append(f"   Published: {pub}")
            if url:
                lines.append(f"   URL: {url}")
            lines.append("")
        return "\n".join(lines)

    # -- Decision response (has 'decision' key) --
    if "decision" in obj and "reasoning" in obj:
        lines.append(f"**Symbol:** {obj.get('symbol', 'N/A')}")
        lines.append(f"**Decision:** {obj.get('decision')} | **Confidence:** {obj.get('confidence', 'N/A')} | **Risk:** {obj.get('risk_level', 'N/A')}")
        lines.append(f"**Reasoning:** {obj.get('reasoning', '')}")
        if obj.get("disclaimer"):
            lines.append(f"*{obj['disclaimer']}*")
        return "\n".join(lines)

    # -- Summary/aggregate response (has nested data) --
    if "aggregated_prompt" in obj:
        lines.append(f"**Symbol:** {obj.get('symbol', 'N/A')}")
        # Show sub-data summaries
        pd = obj.get("price_data")
        if pd and isinstance(pd, dict):
            lines.append(f"**Price:** ${pd.get('price_usd', 0):,.2f} | 24h: {pd.get('change_24h_pct', 0):+.2f}%")
        td = obj.get("trend_data")
        if td and isinstance(td, dict):
            lines.append(f"**Trend ({td.get('days',7)}d):** {td.get('trend','N/A')} | Change: {td.get('change_pct', 0):+.2f}%")
        nd = obj.get("news_data")
        if nd and isinstance(nd, dict) and nd.get("articles"):
            lines.append(f"**News ({nd.get('total_results', 0)} articles):**")
            for i, art in enumerate(nd["articles"], 1):
                lines.append(f"  {i}. {art.get('title', 'N/A')}")
        return "\n".join(lines)

    # -- Price response --
    if "price_usd" in obj:
        name = obj.get("name", obj.get("symbol", ""))
        sym = obj.get("symbol", "")
        lines.append(f"**{name} ({sym}):** ${obj['price_usd']:,.2f}")
        lines.append(f"**24h Change:** {obj.get('change_24h_pct', 0):+.2f}%")
        if obj.get("last_updated"):
            lines.append(f"**Updated:** {obj['last_updated']}")
        return "\n".join(lines)

    # -- Trend response --
    if "trend" in obj and "change_pct" in obj:
        lines.append(f"**{obj.get('symbol', 'N/A')}** -- {obj.get('days', 7)} days")
        lines.append(f"**Trend:** {obj['trend']} | **Change:** {obj['change_pct']:+.2f}%")
        lines.append(f"**Start:** ${obj.get('start_price', 0):,.2f} -> **End:** ${obj.get('end_price', 0):,.2f}")
        lines.append(f"**High:** ${obj.get('high', 0):,.2f} | **Low:** ${obj.get('low', 0):,.2f}")
        return "\n".join(lines)

    # -- Fallback: show all keys --
    for k, v in obj.items():
        if isinstance(v, float):
            v = f"{v:,.2f}" if abs(v) > 1 else f"{v:.4f}"
        lines.append(f"**{k}:** {v}")
    return " | ".join(lines)

def render_step(step: dict, show_raw: bool = False):
    """Render a single ReAct step as a styled card."""
    stype = step.get("type", "thought")
    cfg = STEP_CONFIG.get(stype, STEP_CONFIG["thought"])
    content = _sanitize(step.get("content", ""))
    step_num = step.get("step", 0)
    latency = step.get("latency_ms")

    # Header label
    label = f"Step {step_num} -- {cfg['label']}" if step_num else cfg["label"]

    # Format content based on type
    if stype == "observation":
        if show_raw:
            display_content = f"```json\n{_pretty_json(content)}\n```"
        else:
            try:
                obj = json.loads(content)
                if isinstance(obj, dict):
                    display_content = _format_observation(obj)
                elif isinstance(obj, list):
                    # List of results (e.g. multi_crypto_price)
                    parts = []
                    for item in obj:
                        if isinstance(item, dict):
                            parts.append(_format_observation(item))
                        else:
                            parts.append(str(item))
                    display_content = "\n\n---\n\n".join(parts)
                else:
                    display_content = _pretty_json(content)
            except (json.JSONDecodeError, TypeError):
                display_content = content
    elif stype == "action":
        display_content = f"`{content}`"
    else:
        display_content = content

    # Meta info
    meta_parts = []
    if latency:
        meta_parts.append(f"{latency}ms")
    usage = step.get("usage")
    if usage and isinstance(usage, dict):
        tokens = usage.get("total_tokens")
        if tokens:
            meta_parts.append(f"{tokens} tokens")
    meta_str = " | ".join(meta_parts)

    st.markdown(
        f'<div class="step-card" style="--accent: {cfg["color"]}">'
        f'<div class="step-header" style="color: {cfg["color"]}">'
        f'{label}'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(display_content)
    if meta_str:
        st.caption(meta_str)


for i, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            # Show trace log inside expander
            if i < len(st.session_state.traces) and st.session_state.traces[i]:
                trace = st.session_state.traces[i]
                with st.expander(f"ReAct Log ({len(trace)} steps)", expanded=False):
                    for step in trace:
                        render_step(step, show_raw=show_raw_obs)
            st.markdown(msg["content"])


# -------------------------------------------------------------
# Suggestions (only if no messages)
# -------------------------------------------------------------

if not st.session_state.messages:
    st.markdown("#### Thu hoi:")
    suggestions = [
        "Gia Bitcoin hien tai la bao nhieu?",
        "Phan tich xu huong ETH 7 ngay",
        "Tom tat tinh hinh BTC",
        "Toi co nen mua SOL luc nay khong?",
        "So sanh gia BTC va ETH",
    ]
    cols = st.columns(len(suggestions))
    for j, (col, sug) in enumerate(zip(cols, suggestions)):
        with col:
            if st.button(sug, key=f"sug_{j}", use_container_width=True):
                st.session_state["_pending_input"] = sug
                st.rerun()

# Handle suggestion click
if "_pending_input" in st.session_state:
    pending = st.session_state.pop("_pending_input")
    st.session_state.messages.append({"role": "user", "content": pending})
    st.session_state.traces.append(None)

    agent = st.session_state.agent
    agent.max_steps = max_steps

    trace = []
    final_text = ""

    with st.chat_message("user"):
        st.markdown(pending)

    with st.chat_message("assistant"):
        log_container = st.expander("ReAct Log (dang chay...)", expanded=True)
        answer_placeholder = st.empty()

        with st.spinner("Agent dang suy luan..."):
            for step in agent.run_with_trace(pending):
                trace.append(step)
                with log_container:
                    render_step(step, show_raw=show_raw_obs)

                if step["type"] == "final_answer":
                    final_text = step["content"]
                elif step["type"] in ("scope_reject", "error", "max_steps"):
                    final_text = step["content"]

        answer_placeholder.markdown(_sanitize(final_text))

    st.session_state.messages.append({"role": "assistant", "content": _sanitize(final_text)})
    st.session_state.traces.append(trace)
    st.rerun()


# -------------------------------------------------------------
# Chat input
# -------------------------------------------------------------

user_input = st.chat_input("Hoi ve crypto... (VD: Gia Bitcoin bao nhieu?)")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.traces.append(None)

    agent = st.session_state.agent
    agent.max_steps = max_steps

    trace = []
    final_text = ""

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        log_container = st.expander("ReAct Log (dang chay...)", expanded=True)
        answer_placeholder = st.empty()

        with st.spinner("Agent dang suy luan..."):
            for step in agent.run_with_trace(user_input):
                trace.append(step)
                with log_container:
                    render_step(step, show_raw=show_raw_obs)

                if step["type"] == "final_answer":
                    final_text = step["content"]
                elif step["type"] in ("scope_reject", "error", "max_steps"):
                    final_text = step["content"]

        answer_placeholder.markdown(_sanitize(final_text))

    st.session_state.messages.append({"role": "assistant", "content": _sanitize(final_text)})
    st.session_state.traces.append(trace)
    st.rerun()
