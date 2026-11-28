const path = require("path");

module.exports = {
  plugins: {
    // Chỉ rõ file cấu hình: không thì Tailwind tìm theo thư mục chạy lệnh
    // (process.cwd()), trong Docker là /app nên rơi về theme mặc định.
    tailwindcss: { config: path.join(__dirname, "tailwind.config.js") },
    autoprefixer: {},
  },
}
