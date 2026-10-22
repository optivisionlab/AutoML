FROM node:22-bookworm-slim

WORKDIR /app

# Install all workspaces before mounting their source in development.
COPY package.json package-lock.json ./
# Next chạy từ /app nên Tailwind/PostCSS tìm cấu hình ở đây (hai file này trỏ
# sang apps/web). Thiếu chúng, Tailwind dùng theme mặc định và lỗi `border-border`.
COPY tailwind.config.js postcss.config.js ./
COPY apps/ ./apps/
COPY packages/ ./packages/
RUN npm ci --no-audit --no-fund

ENV NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
