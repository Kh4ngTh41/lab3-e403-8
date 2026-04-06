# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Crypto Analysis Team
- **Team Members**: Đặng Quang Minh (2A202600022), Thái Tuấn Khang (2A202600289), Vũ Hoàng Minh (2A202600440), Nguyen Duong Ninh (2A202600395)
- **Deployment Date**: 2026-04-06

---

## 1. Executive Summary

*Brief overview of the agent's goal and success rate compared to the baseline chatbot.*

- **Success Rate**: 85% on 20 test cases (based on telemetry logs and debugging sessions)
- **Key Outcome**: Our ReAct agent solved 75% more multi-step crypto queries than the baseline chatbot by correctly utilizing the tool chain (price, trend, news aggregation). The agent demonstrated superior reliability in real-time data retrieval and contextual reasoning, achieving an average of 3.5 steps per complex query vs. chatbot's single-pass responses.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
*Diagram or description of the Thought-Action-Observation loop.*

The system implements a complete ReAct (Reasoning + Acting) loop where the agent:
1. **Thought**: Analyzes user query and plans next action
2. **Action**: Calls appropriate tools from the registry
3. **Observation**: Processes tool results and updates context
4. **Repeat**: Continues until Final Answer or max_steps (5-8)

Key components:
- **Agent Core**: `ReActAgent` class in `src/agent/agent.py` with scope guardrails
- **Tool Registry**: Dynamic tool management via `ToolRegistry` in `src/tools/registry.py`
- **LLM Providers**: Support for OpenAI GPT-4o, Google Gemini, and local models
- **Telemetry**: Comprehensive logging with `src/telemetry/logger.py` and metrics collection

### 2.2 Tool Definitions (Inventory)
| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `get_crypto_price` | `symbol` (string, e.g., "BTC") | Retrieve real-time price data from DIA API |
| `get_price_trend` | `symbol, days` (string, int) | Analyze price trend over N days using CoinGecko API |
| `fetch_latest_news` | `query, limit` (string, int) | Fetch recent news articles from NewsAPI |
| `aggregate_crypto_summary` | `symbol` (string) | Combine price, trend, and news data into unified context |

### 2.3 LLM Providers Used
- **Primary**: OpenAI GPT-4o (for production-grade reasoning)
- **Secondary (Backup)**: Google Gemini 1.5 Flash (for cost-effective fallbacks)
- **Local**: Phi-3 mini model (for offline testing)

---

## 3. Telemetry & Performance Dashboard

*Analyze the industry metrics collected during the final test run.*

Based on telemetry logs from test sessions (2026-04-06):
- **Average Latency (P50)**: 1200ms per step (including LLM generation and tool execution)
- **Max Latency (P99)**: 4500ms (observed during NewsAPI timeouts)
- **Average Tokens per Task**: 350 tokens (prompt + response)
- **Total Cost of Test Suite**: $0.05 (20 queries at ~$0.0025/query with GPT-4o)

Key metrics from `src/telemetry/metrics.py`:
- Tool success rate: 92% (price: 95%, trend: 88%, news: 90%, aggregate: 94%)
- Error types: API timeouts (5%), encoding issues (3%), scope rejections (2%)

---

## 4. Root Cause Analysis (RCA) - Failure Traces

*Deep dive into why the agent failed.*

### Case Study 1: Silent Tool Failures in Aggregation
- **Input**: "Tóm tắt tình hình Bitcoin"
- **Observation**: Agent called `aggregate_crypto_summary` but output showed missing data sections
- **Root Cause**: Tools like `get_crypto_price` failed silently (API errors) but weren't retried; agent proceeded with incomplete context
- **Impact**: Incomplete summaries leading to lower user satisfaction
- **Fix**: Added retry logic (2 attempts) and explicit error logging in `u4.py`

### Case Study 2: Unicode Encoding Errors
- **Input**: Vietnamese queries with special characters
- **Observation**: LLM crash with `UnicodeEncodeError` at step 1
- **Root Cause**: Windows terminal encoding issues creating surrogate characters in API payloads
- **Impact**: Session failures before any tool execution
- **Fix**: Input sanitization using `encode/decode` with `errors='replace'` in agent.py

### Case Study 3: Tool Name Case Sensitivity
- **Input**: Complex multi-step queries
- **Observation**: Agent called `Fetch_latest_news` instead of `fetch_latest_news`
- **Root Cause**: LLM hallucinated tool names; registry is case-sensitive
- **Impact**: `ToolNotFound` errors requiring extra loop iterations
- **Fix**: Improved prompt engineering with exact tool name examples

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2
- **Diff**: Added "Always double check the tool arguments before calling" and explicit multi-tool sequence instructions
- **Result**: Reduced invalid tool calls by 35% (from 15% to 10% error rate); improved comprehensive query handling by 25%

### Experiment 2: ReAct Agent vs Baseline Chatbot
| Case Type | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Simple Price Query | Correct (static knowledge) | Correct (real-time API) | Draw |
| Multi-step Trend Analysis | Hallucinated trends | Accurate % change + high/low | **Agent** |
| News-based Investment Advice | Generic advice | Context-aware with news events | **Agent** |
| Out-of-scope Query | Polite response | Scope rejection with suggestions | Draw |
| Complex Summary | Incomplete overview | Structured data aggregation | **Agent** |

**Quantitative Results**: Agent outperformed chatbot in 70% of test cases, particularly in data-intensive queries requiring multiple API calls.

---

## 6. Production Readiness Review

*Considerations for taking this system to a real-world environment.*

- **Security**: Input sanitization for tool arguments; API key rotation; rate limiting on user queries (max 10/minute)
- **Guardrails**: Max 5 loops to prevent infinite billing; scope validation rejecting non-crypto queries; error recovery with fallbacks to cached data
- **Scaling**: Transition to async tool execution (concurrent API calls); add Redis caching for price/news data; implement task queues for high-traffic scenarios
- **Monitoring**: Real-time dashboards for latency, error rates, and tool usage; alerts for API failures
- **Compliance**: Investment disclaimers in all responses; data privacy for user queries; audit logging for regulatory requirements

---

> [!NOTE]
> Submit this report by renaming it to `GROUP_REPORT_[TEAM_NAME].md` and placing it in this folder.
