import asyncio
import os
from hagent.agent.graph import run_agent
from hagent.agent.registry import reset_registry, get_agent_registry

async def main():
    print("=== Khởi tạo Agent Registry ===")
    reset_registry()
    get_agent_registry()
    
    print("\n=== Bước 1: Gửi yêu cầu training tới Agent ===")
    msg1 = "Hãy tìm dataset 'student', sau đó chạy training với 3 thuật toán Random Forest, XGBoost và SVM. Nếu job đang chạy, hãy lấy kết quả."
    print(f"User: {msg1}")
    res1 = await run_agent(msg1, user_id="github_action_user")
    
    print("\n[Agent Output 1]:")
    print(res1.get("messages", [])[-1].content)
    
    print("\n=== Bước 2: Yêu cầu giải thích và xuất Markdown ===")
    msg2 = "Tuyệt vời. Dựa vào các kết quả training đã nhận được, hãy giải thích chi tiết tại sao thuật toán tốt nhất lại phù hợp cho bài toán phân loại học sinh (student). Sau đó, hãy tạo một báo cáo Markdown hoàn chỉnh, có bảng so sánh, và xuất ra nội dung file."
    print(f"User: {msg2}")
    res2 = await run_agent(msg2, user_id="github_action_user")
    
    out2 = res2.get("messages", [])[-1].content
    print("\n[Agent Output 2 - Markdown Report]:")
    print(out2)
    
    # Save the report
    out_dir = os.path.join(os.path.dirname(__file__), "../docs")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "Student_Training_Report.md")
    
    # Lọc phần markdown nếu agent viết thêm text
    md_content = out2
    if "```markdown" in out2:
        md_content = out2.split("```markdown")[1].split("```")[0].strip()
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n✓ Report saved to {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
