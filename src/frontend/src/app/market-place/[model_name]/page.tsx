"use client";

import { useParams } from "next/navigation";

import { MarketplaceModelDetail } from "@/types/marketplace";
import { useState } from "react";
import InferenceAPI from "@/components/marketplace/model/InterfaceApi";
import Details from "@/components/marketplace/model/Details";
import PerformanceEvaluation from "@/components/marketplace/model/PerformanceEvaluation";
import AccessRestrictions from "@/components/marketplace/model/AccessRestrictions";
import Review from "@/components/marketplace/model/Review";
import Image from "next/image";
import { useRouter } from "next/navigation";
import toSlug from "@/utils/toSlug";

export const marketplaceModels: MarketplaceModelDetail[] = [
  {
    id: "1",
    slug: "gpt-4-turbo",
    name: "GPT-4 Turbo",
    img: "https://cdn.prod.website-files.com/66841c2a95405226a60d332e/67c6daab82fff6c435bc3e9b_deepseek_R1.webp",
    shortDescription:
      "Mô hình OCR AI nhận dạng và trích xuất văn bản từ ảnh và PDF.",
    description:
      "DeepSeek OCR là mô hình AI chuyên xử lý tài liệu hình ảnh và PDF với khả năng nhận dạng văn bản, bảng biểu và bố cục phức tạp. Phù hợp cho doanh nghiệp số hóa tài liệu, hóa đơn, hợp đồng và biểu mẫu.",
    category: "Vision AI",
    provider: "DeepSeek",
    tags: ["OCR", "PDF", "Document AI", "Vision"],
    supportedFormats: ["PNG", "JPG", "PDF"],
    features: [
      "Nhận dạng văn bản đa ngôn ngữ",
      "Giữ nguyên cấu trúc bảng và bố cục",
      "Hỗ trợ tài liệu scan chất lượng thấp",
      "Xuất kết quả dạng Text, Markdown, CSV",
    ],
    specs: [
      { label: "Đầu vào", value: "Ảnh, PDF" },
      { label: "Đầu ra", value: "Text / Markdown / CSV" },
      { label: "Ngôn ngữ", value: "100+ ngôn ngữ" },
      { label: "Độ chính xác", value: "Cao" },
      { label: "Độ trễ", value: "< 2s / tài liệu" },
    ],
    pricing: [
      {
        name: "Free",
        price: "Miễn phí",
        description: "Giới hạn số request, phù hợp thử nghiệm",
      },
      {
        name: "Pro",
        price: "Theo lượt sử dụng",
        description: "Xử lý nhanh, file lớn",
        highlight: true,
      },
      {
        name: "Enterprise",
        price: "Liên hệ",
        description: "SLA, hỗ trợ doanh nghiệp, tích hợp riêng",
      },
    ],
  },
];

const TABS = [
  { key: "inference_api", label: "Inference API" },
  { key: "details", label: "Chi tiết" },
  { key: "performance_evaluation", label: "Đánh giá hiệu năng" },
  { key: "access_restrictions", label: "Giới hạn truy cập" },
  { key: "review", label: "Đánh giá" },
];

export default function MarketplaceDetailPage() {
  const params = useParams();
  const router = useRouter();

  const model = marketplaceModels.find(
    (m) => m.slug === (params?.model_name as string)
  );

  if (!model) {
    return <div className="p-10">Không tìm thấy model</div>;
  }

  // active tabs
  const [activeTab, setActiveTab] = useState("inference_api");

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 space-y-10">
      {/* Header */}
      <div className="flex justify-between items-start bg-[#F9FAFB] p-6 rounded-lg">
        <div className="flex items-center gap-6">
          <div className="w-34 h-34 bg-white aspect-square border rounded-lg flex items-center justify-center overflow-hidden">
            <Image
              src={model.img}
              alt={model.name}
              width={100}
              height={100}
              className="w-full h-full object-contain"
            />
          </div>
          <div>
            <h1 className="text-3xl font-semibold text-gray-900">
              {model.name}
            </h1>
            <p className="text-gray-600 mt-2">{model.shortDescription}</p>
            <div className="flex gap-2 mt-3">
              {model.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-1 bg-gray-100 rounded"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <button
          onClick={() => router.push(`/playground?model=${toSlug(model.name)}`)}
          className="px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Dùng thử model
        </button>
      </div>

      <div className="text-sm text-gray-600">{model.description}</div>

      {/* Tab nội dung */}
      <div className="space-y-6 min-h-[500px]">
        {/* Tabs */}
        <nav className="flex gap-6 border-b">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium transition
            ${
              activeTab === tab.key
                ? "border-b-2 border-blue-600 text-blue-600 translate-x-0 duration-200"
                : "text-gray-500 hover:text-gray-900"
            }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        {activeTab === "inference_api" && (
          <InferenceAPI description={model.description} />
        )}
        {activeTab === "details" && <Details model={model} />}
        {activeTab === "performance_evaluation" && <PerformanceEvaluation />}
        {activeTab === "access_restrictions" && <AccessRestrictions />}
        {activeTab === "review" && <Review />}
      </div>

      {/* Model liên quan */}
      <hr />
      <h1>Model liên quan</h1>
    </div>
  );
}
