export default function toTitleLabel(text) {
  return text
    .replace(/[-_]+/g, " ") // đổi - và _ thành khoảng trắng
    .toLowerCase() // đưa về chữ thường
    .split(" ")
    .filter(Boolean) // bỏ khoảng trắng thừa
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
