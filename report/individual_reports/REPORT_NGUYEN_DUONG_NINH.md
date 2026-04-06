# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyen Duong Ninh
- **Student ID**: 2A202600395
- **Date**: 04/03/2003

---

## I. Technical Contribution (15 Points)


- **Modules Implementated**: src\tools\u3.py
- **Code Highlights**: _get_news_api_key(), fetch_latest_news(
    query: str = "Bitcoin",
    limit: int = 5,
) -> Union[NewsOutput, ToolError]
- **Documentation**: la tool keo tin tuc ve cho con agent

---

## II. Debugging Case Study (10 Points)
Problem Description: Agent bị lỗi khi gọi tool với query rỗng hoặc input không hợp lệ, dẫn đến API trả về lỗi hoặc kết quả rỗng
Log Source: logs runtime của tool fetch_latest_news
Diagnosis: LLM chưa validate input tốt, dẫn đến gọi tool sai format hoặc thiếu context
Solution: thêm validate bằng NewsInput, xử lý error rõ ràng (ConfigError, TimeoutError, HTTPError)

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)
Reasoning: Thought block giúp agent suy luận từng bước trước khi gọi tool, thay vì trả lời trực tiếp như chatbot
Reliability: Agent đôi khi chậm hơn chatbot, nhưng chính xác hơn khi cần dữ liệu thật từ tool
Observation: Output từ tool (news data) ảnh hưởng trực tiếp đến bước suy luận tiếp theo của agent

---

## IV. Future Improvements (5 Points)
Cải thiện logic crawl dữ liệu để giảm độ trễ và tăng chất lượng tin
Thêm caching để tránh gọi API nhiều lần
Tối ưu prompt để agent phân tích tin chính xác hơn

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
