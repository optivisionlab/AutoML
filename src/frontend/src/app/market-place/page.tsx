"use client";

import MarketplaceCard from "@/components/marketplace/MarketplaceCard";
import MarketplaceHeader from "@/components/marketplace/MarketplaceHeader";
import React, { useState } from "react";

const categories = [
  { id: "all", name: "Tất cả dịch vụ" },
  { id: "text", name: "Text AI" },
  { id: "image", name: "Image AI" },
  { id: "audio", name: "Audio AI" },
  { id: "video", name: "Video AI" },
];

const models = [
  {
    id: 1,
    name: "GPT-4 Turbo",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    description: "Mô hình AI xử lý ngôn ngữ tự nhiên, tối ưu cho doanh nghiệp.",
    category: "text",
    price: "Trả phí",
    provider: "OpenAI",
  },
  {
    id: 2,
    name: "Claude 3",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    description:
      "AI hội thoại thông minh, an toàn cho môi trường doanh nghiệp.",
    category: "text",
    price: "Trả phí",
    provider: "Anthropic",
  },
  {
    id: 3,
    name: "DALL·E",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    description: "Dịch vụ tạo hình ảnh AI từ văn bản.",
    category: "image",
    price: "Miễn phí",
    provider: "OpenAI",
  },
  {
    id: 4,
    name: "Stable Diffusion",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    description: "Nền tảng tạo ảnh AI mã nguồn mở.",
    category: "image",
    price: "Miễn phí",
    provider: "Community",
  },
  {
    id: 5,
    name: "Whisper",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    description: "Nhận dạng và chuyển giọng nói thành văn bản.",
    category: "audio",
    price: "Miễn phí",
    provider: "OpenAI",
  },
];

export default function MarketplacePage() {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const filteredModels =
    selectedCategory === "all"
      ? models
      : models.filter((m) => m.category === selectedCategory);

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      {/* Header */}
      <MarketplaceHeader searchValue={search} onSearchChange={setSearch} />

      {/* Content */}
      <div className="max-w-8xl mx-auto px-10 py-8 grid grid-cols-12 gap-6">
        {/* Sidebar */}
        <aside className="col-span-12 md:col-span-2">
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              Danh mục dịch vụ
            </h2>

            <ul className="space-y-1">
              {categories.map((cat) => (
                <li
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-3 rounded-md text-sm cursor-pointer transition border-l-4
                    ${
                      selectedCategory === cat.id
                        ? "bg-blue-50 text-blue-600 font-medium border-l-4 border-blue-600"
                        : "text-gray-600 hover:bg-gray-100"
                    }
                  `}
                >
                  {cat.name}
                </li>
              ))}
            </ul>
          </div>
        </aside>

        {/* Main */}
        {models.length === 0 ? (
          <div className="col-span-12 md:col-span-10 text-center text-[#fff]">
            Không có dịch vụ nào trong danh mục này.
          </div>
        ) : (
          <main className="col-span-12 md:col-span-10">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredModels.map((model) => (
                <MarketplaceCard key={model.id} model={model} />
              ))}
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
