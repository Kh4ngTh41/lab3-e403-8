# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đặng Quang Minh
- **Student ID**: 2A202600022
- **Date**: 06/04/2026

---

## I. Technical Contribution (15 Points)



- **Modules Implementated**: [e.g., `src/tools/u4.py`]
- **Code Highlights**: 

    def aggregate_crypto_summary(symbol: str = "BTC"):
    price_result = get_crypto_price(sym)
    trend_result = get_price_trend(sym, days=7)
    news_result = fetch_latest_news(query=sym, limit=3)

    Tool UC4 thực hiện:
Gọi 3 tool khác (UC1, UC2, UC3)
Gom dữ liệu lại thành 1 context

sections = []

if price_data:
    sections.append(f"[GIA HIEN TAI] ...")
else:
    sections.append("[GIA HIEN TAI] Khong lay duoc du lieu gia.")

    Điểm quan trọng:

Có graceful degradation
Không crash khi thiếu data

aggregated_prompt = (
    f"Bạn là chuyên gia phân tích Crypto..."
    + "\n".join(sections)
)

Output không phải final answer
→ mà là prompt cho LLM reasoning


- **Documentation**: 
UC4 đóng vai trò là Aggregator Tool trong ReAct Agent

Flow trong ReAct loop:

Thought: cần summary toàn diện
Action: gọi aggregate_crypto_summary
Observation: nhận aggregated_prompt
Thought: generate final answer

Cụ thể:

Agent gọi UC4 khi user hỏi:
→ "Tóm tắt tình hình Bitcoin"
UC4:
gọi UC1 → lấy giá
gọi UC2 → lấy xu hướng
gọi UC3 → lấy tin tức
Gom tất cả thành:
structured context
prompt cho LLM

👉 Đây là bước:
Tool composition + Context building
---

## II. Debugging Case Study (10 Points)

Problem Description

Agent trả về kết quả thiếu thông tin:

[GIA HIEN TAI] Khong lay duoc du lieu gia.
[XU HUONG] Khong lay duoc du lieu trend.
Log Source
[TOOL_CALL] aggregate_crypto_summary
[TOOL_RESULT] has_price=False, has_trend=False, has_news=True

(Theo logger trong code )

Diagnosis

Nguyên nhân chính:

Tool UC1 hoặc UC2 fail nhưng:

if isinstance(price_result, CryptoPriceOutput):
    price_data = price_result

→ Nếu fail → bị bỏ qua silent

Không có retry mechanism
Agent không biết:
→ tool fail hay data không tồn tại

👉 Đây là vấn đề:
Silent failure trong tool chaining

Solution
1. Thêm logging chi tiết hơn
if not price_data:
    logger.log_event("WARNING", {"missing": "price"})
2. Thêm retry logic
for _ in range(2):
    result = get_crypto_price(sym)
    if isinstance(result, CryptoPriceOutput):
        break
3. Improve prompt
If any section is missing, explicitly mention data limitation
4. Improve agent logic
if not result.has_price:
    call_tool("get_crypto_price")

👉 Sau fix:

Agent hiểu rõ missing data
Output đáng tin hơn

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. Reasoning

Chatbot:

Trả lời trực tiếp từ LLM
Không kiểm chứng dữ liệu

ReAct:

Thought → cần dữ liệu
Action → gọi tool
Observation → cập nhật context
→ trả lời

👉 UC4 cho thấy:

reasoning không phải 1 bước
mà là pipeline nhiều bước
2. Reliability

ReAct có thể kém hơn khi:

Tool fail (như UC1, UC2)
API lỗi
Không có retry

Ví dụ trong UC4:

thiếu price → summary sai

👉 Chatbot có thể "trả lời mượt hơn"
nhưng không đảm bảo đúng

3. Observation

Observation trong UC4 là:

TOOL_RESULT → has_price / has_trend / has_news

👉 Đây là feedback cực kỳ quan trọng

Ví dụ:

has_price=False
→ agent nên gọi lại UC1

👉 Observation giúp:

agent tự sửa lỗi
tránh hallucination

## IV. Future Improvements (5 Points)

Scalability
Tách UC4 thành pipeline async:
parallel call UC1, UC2, UC3
Sử dụng task queue (Celery / asyncio)
Safety
Validate output trước khi trả:
assert result.price_data is not None
Thêm Supervisor Agent kiểm tra output
Performance
Cache:
price (1 phút)
news (10 phút)
Giảm số lần gọi API
Advanced Improvements
Convert sang graph-based agent (LangGraph style)
Multi-agent:
Data agent
Summary agent
Decision agent

UC4 là:

👉 Tool quan trọng nhất trong hệ thống

Vì nó:

kết nối tất cả tool khác
tạo context cho LLM
thể hiện rõ ReAct pattern