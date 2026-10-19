"use client";

import { useState } from "react";
import {
  ArrowRight,
  BrainCircuit,
  Check,
  Code2,
  Copy,
  Cpu,
  Database,
  ExternalLink,
  Github,
  Key,
  Layers,
  Rocket,
  Sparkles,
  Terminal,
  Workflow,
  Boxes,
  FileText,
  LayoutDashboard,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { useLanguage } from "@/core/i18n/LanguageProvider";
import {
  LAB_INFO,
  RELEASES_LIST,
  getFeatureCards,
  getQuickstartSteps,
} from "../data/docs-content";
import { INDEX_MD } from "../data/markdown-docs";
import { INDEX_MD_EN } from "../data/markdown-docs-en";
import MarkdownRenderer from "./MarkdownRenderer";

type DocsOverviewProps = {
  onSelectTopic: (topicId: string) => void;
};

const iconMap: Record<string, React.ElementType> = {
  Database,
  BrainCircuit,
  Rocket,
  Workflow,
  Code2,
  Sparkles,
  Cpu,
  Layers,
  Boxes,
};

export default function DocsOverview({ onSelectTopic }: DocsOverviewProps) {
  const t = useTranslations("Docs");
  const { locale } = useLanguage();

  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [copiedMarkdown, setCopiedMarkdown] = useState<boolean>(false);
  const [activeQuickTab, setActiveQuickTab] = useState<number>(0);
  const [viewMode, setViewMode] = useState<"interactive" | "markdown">("interactive");

  const featureCards = getFeatureCards(locale);
  const quickstartSteps = getQuickstartSteps(locale);
  const currentMarkdown = locale === "en" ? INDEX_MD_EN : INDEX_MD;

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(currentMarkdown);
    setCopiedMarkdown(true);
    setTimeout(() => setCopiedMarkdown(false), 2000);
  };

  return (
    <div className="space-y-10 rounded-3xl border border-slate-200/80 bg-white/70 p-6 sm:p-8 backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
      {/* 1. Header Toolbar & Mode Switcher (No duplicate BreadcrumbNav) */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200/70 pb-4 dark:border-white/10">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-600 dark:bg-blue-950/60 dark:text-cyan-400 border border-blue-200/60 dark:border-blue-800/40">
            <Sparkles className="h-3.5 w-3.5" />
            {t("overview.labName")}
          </div>
          <h1 className="mt-2 text-2xl sm:text-3xl font-black tracking-tight text-slate-900 dark:text-white">
            {t("overview.welcome")}
          </h1>
        </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 rounded-xl border border-slate-200/80 bg-slate-100/90 p-1 dark:border-white/10 dark:bg-white/5">
              <button
                type="button"
                onClick={() => setViewMode("interactive")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  viewMode === "interactive"
                    ? "bg-white text-blue-600 shadow-sm dark:bg-[#061021] dark:text-cyan-400"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                <LayoutDashboard className="h-3.5 w-3.5" />
                <span>{t("interactiveView")}</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("markdown")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  viewMode === "markdown"
                    ? "bg-white text-blue-600 shadow-sm dark:bg-[#061021] dark:text-cyan-400"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>{t("markdownView")}</span>
              </button>
            </div>

            {/* Quick Links */}
            {viewMode === "markdown" && (
              <button
                type="button"
                onClick={handleCopyMarkdown}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-[#061021] dark:text-slate-200 dark:hover:bg-white/5"
              >
                {copiedMarkdown ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                    <span className="text-emerald-500 font-bold">{t("copiedMarkdown")}</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>{t("copyMarkdown")}</span>
                  </>
                )}
              </button>
            )}

            <a
              href={LAB_INFO.docsUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200/70 bg-blue-50/60 px-3 py-1.5 text-xs font-bold text-blue-700 transition hover:bg-blue-100/70 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-cyan-400"
            >
              <span>{t("mkdocsOnline")}</span>
              <ExternalLink className="h-3 w-3" />
            </a>
            <a
              href={LAB_INFO.github}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-[#061021] dark:text-slate-200 dark:hover:bg-white/5"
            >
              <Github className="h-3.5 w-3.5" />
              <span>{t("github")}</span>
            </a>
          </div>
        </div>

      {/* Conditionally Render: Full Markdown or Interactive View */}
      {viewMode === "markdown" ? (
        <div className="space-y-6">
          <div className="flex items-center gap-2 rounded-2xl border border-emerald-300/60 bg-emerald-50/60 px-4 py-2 text-xs font-medium text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200">
            <Sparkles className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span>{t("officialMirrorIndex")}</span>
          </div>

          <MarkdownRenderer content={currentMarkdown} />

          <div className="flex justify-end pt-6 border-t border-slate-200/80 dark:border-white/10">
            <button
              type="button"
              onClick={() => onSelectTopic("getting-started")}
              className="group inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-5 py-3 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500"
            >
              <span>
                {t("nextPage")}: {t("tabs.gettingStarted")}
              </span>
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-12">
          {/* Welcome Description */}
          <div className="space-y-4">
            <p className="text-sm sm:text-base leading-relaxed text-slate-700 dark:text-slate-300">
              {locale === "en" ? (
                <>
                  <strong>HAutoML</strong> is an open-source <strong>Automated Machine Learning (AutoML)</strong> platform developed by{" "}
                  <a
                    href={LAB_INFO.website}
                    target="_blank"
                    rel="noreferrer"
                    className="font-bold text-blue-600 underline hover:text-blue-700 dark:text-cyan-400"
                  >
                    OptiVisionLab
                  </a>
                  , School of Information and Communications Technology, Hanoi University of Industry.
                </>
              ) : (
                <>
                  <strong>HAutoML</strong> là nền tảng <strong>tự động hóa học máy (Automated Machine Learning - AutoML)</strong> mã nguồn mở được phát triển bởi{" "}
                  <a
                    href={LAB_INFO.website}
                    target="_blank"
                    rel="noreferrer"
                    className="font-bold text-blue-600 underline hover:text-blue-700 dark:text-cyan-400"
                  >
                    OptiVisionLab
                  </a>
                  , Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội.
                </>
              )}
            </p>

            <p className="text-xs sm:text-sm leading-relaxed text-slate-600 dark:text-slate-400">
              {locale === "en" ? (
                <>
                  The platform automates the entire machine learning workflow — from data preprocessing, model selection, hyperparameter tuning, to model deployment — enabling users to easily build high-accuracy models{" "}
                  <strong className="text-slate-900 dark:text-white">without requiring in-depth expertise in programming or data science</strong>.
                </>
              ) : (
                <>
                  Nền tảng này tự động hóa toàn bộ quy trình xây dựng mô hình học máy - từ tiền xử lý dữ liệu, lựa chọn mô hình, tinh chỉnh siêu tham số, cho đến triển khai mô hình - cho phép người dùng dễ dàng tải dữ liệu lên và tự động tạo ra các mô hình học máy chất lượng cao{" "}
                  <strong className="text-slate-900 dark:text-white">mà không cần kiến thức sâu về lập trình hay khoa học dữ liệu</strong>.
                </>
              )}
            </p>

            {/* Read full markdown prompt banner */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-2xl border border-blue-200/80 bg-blue-50/60 p-4 text-xs text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200">
              <div className="flex items-center gap-2.5">
                <FileText className="h-4 w-4 text-blue-600 dark:text-cyan-400 shrink-0" />
                <span>{t("readFullMarkdownPrompt")}</span>
              </div>
              <button
                type="button"
                onClick={() => setViewMode("markdown")}
                className="inline-flex items-center gap-1 font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400 shrink-0 underline"
              >
                <span>{t("readFullMarkdownAction")}</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            {/* Vision Callout Box */}
            <div className="rounded-2xl border border-blue-200/80 bg-blue-50/60 p-4.5 text-xs text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-200">
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-blue-500/15 text-blue-600 dark:text-cyan-400">
                  <Key className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-bold text-slate-900 dark:text-white text-sm">
                    🎯 {t("overview.visionTitle")}
                  </p>
                  <p className="mt-1 leading-relaxed">
                    {locale === "en" ? (
                      <>
                        HAutoML is designed to <strong>democratize machine learning</strong> — enabling anyone (students, business analysts, domain experts) to build effective machine learning models without needing to master complex low-level engineering details.
                      </>
                    ) : (
                      <>
                        HAutoML được thiết kế để <strong>dân chủ hóa học máy</strong> - giúp bất cứ ai (dù là sinh viên, nhân viên kinh doanh, hoặc chuyên gia) có thể xây dựng các mô hình học máy hiệu quả mà không cần phải thành thạo các chi tiết kỹ thuật phức tạp.
                      </>
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* 2. Key Features 6-Card Grid */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                ✨ {t("overview.keyFeatures")}
              </h2>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featureCards.map((card) => {
                const IconComp = iconMap[card.icon] || Sparkles;

                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => onSelectTopic(card.topicId)}
                    className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-slate-200/80 bg-white/80 p-5 text-left shadow-sm backdrop-blur-xl transition-all duration-200 hover:-translate-y-1 hover:border-blue-400/60 hover:shadow-[0_12px_32px_rgba(37,99,255,0.12)] dark:border-white/10 dark:bg-[#061021]/80 dark:hover:border-blue-500/50"
                  >
                    <div>
                      <div className="relative mb-4 flex h-24 w-full items-center justify-center overflow-hidden rounded-xl border border-slate-100 bg-slate-50/80 dark:border-white/5 dark:bg-[#030914]">
                        <div
                          className="absolute inset-0 opacity-40 dark:opacity-25"
                          style={{
                            backgroundImage:
                              "linear-gradient(to right, rgba(0, 140, 255, 0.2) 1px, transparent 1px), linear-gradient(to bottom, rgba(0, 140, 255, 0.2) 1px, transparent 1px)",
                            backgroundSize: "20px 20px",
                          }}
                        />
                        <div className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 shadow-md border border-blue-200/50 transition-transform duration-200 group-hover:scale-110 dark:bg-blue-950/70 dark:text-cyan-400 dark:border-blue-700/40 dark:shadow-[0_0_20px_rgba(0,183,255,0.25)]">
                          <IconComp className="h-5 w-5" />
                        </div>
                      </div>

                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                          {card.title}
                        </h3>
                        {card.tag && (
                          <span className="rounded-lg bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-600 dark:bg-blue-950/60 dark:text-blue-300">
                            {card.tag}
                          </span>
                        )}
                      </div>

                      <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                        {card.desc}
                      </p>
                    </div>

                    <div className="mt-4 flex items-center gap-1 text-xs font-bold text-blue-600 opacity-0 transition-opacity group-hover:opacity-100 dark:text-cyan-400">
                      <span>{t("overview.exploreDetails")}</span>
                      <ArrowRight className="h-3 w-3" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Scientific Approach Summary */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                🔬 {t("overview.scientificApproach")}
              </h2>
              <button
                type="button"
                onClick={() => onSelectTopic("scientific-approach")}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400"
              >
                <span>{t("overview.viewDetails")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4.5 dark:border-white/10 dark:bg-[#061021]/60">
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-cyan-400">
                  {locale === "en" ? "1. Intelligent Preprocessing" : "1. Tiền xử lý thông minh"}
                </h3>
                <ul className="mt-2.5 list-inside list-disc text-xs text-slate-600 space-y-1 dark:text-slate-400">
                  {locale === "en" ? (
                    <>
                      <li>Automatic feature type detection (numeric, categorical, text)</li>
                      <li>Adaptive missing value imputation (median / mode)</li>
                      <li>StandardScaler & OneHotEncoder normalization</li>
                      <li>ColumnTransformer pipeline preventing data leakage</li>
                    </>
                  ) : (
                    <>
                      <li>Phát hiện tự động kiểu dữ liệu (số, phân loại, văn bản)</li>
                      <li>Xử lý giá trị thiếu (median cho numeric, mode cho categorical)</li>
                      <li>Chuẩn hóa StandardScaler và OneHotEncoder</li>
                      <li>Pipeline đóng gói chống data leakage</li>
                    </>
                  )}
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4.5 dark:border-white/10 dark:bg-[#061021]/60">
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-cyan-400">
                  {locale === "en" ? "2. Hyperparameter Tuning" : "2. Tìm kiếm siêu tham số"}
                </h3>
                <ul className="mt-2.5 list-inside list-disc text-xs text-slate-600 space-y-1 dark:text-slate-400">
                  {locale === "en" ? (
                    <>
                      <li>Grid Search & Random Search</li>
                      <li>Bayesian Optimization (BO) & Genetic Algorithm (GA)</li>
                      <li>$k$-fold cross-validation ($k=5$)</li>
                      <li>Balancing accuracy vs compute efficiency</li>
                    </>
                  ) : (
                    <>
                      <li>Grid Search & Random Search</li>
                      <li>Bayesian Optimization (BO) & Genetic Algorithm (GA)</li>
                      <li>Kiểm định chéo k-fold cross-validation (k=5)</li>
                      <li>Cân bằng giữa độ chính xác và thời gian tính toán</li>
                    </>
                  )}
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4.5 dark:border-white/10 dark:bg-[#061021]/60">
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-cyan-400">
                  {locale === "en" ? "3. Multi-Criteria Evaluation" : "3. Đánh giá đa tiêu chí"}
                </h3>
                <ul className="mt-2.5 list-inside list-disc text-xs text-slate-600 space-y-1 dark:text-slate-400">
                  {locale === "en" ? (
                    <>
                      <li>Classification: Accuracy, Precision, Recall, F1, Balanced Acc</li>
                      <li>Regression: MAE, MSE, RMSE, $R^2$ Score</li>
                      <li>Generalization validation against overfitting</li>
                      <li>Automated selection of champion model</li>
                    </>
                  ) : (
                    <>
                      <li>Phân loại: Accuracy, Precision, Recall, F1, Balanced Accuracy</li>
                      <li>Hồi quy: MAE, MSE, RMSE, R² Score</li>
                      <li>Xác thực generalization tránh overfitting</li>
                      <li>Chọn mô hình có điểm số cao nhất</li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          </div>

          {/* 4. Quickstart Guide */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Rocket className="h-5 w-5 text-blue-600 dark:text-cyan-400" />
                {t("overview.quickstart")}
              </h2>
              <button
                type="button"
                onClick={() => onSelectTopic("getting-started")}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400"
              >
                <span>{t("overview.viewFullGuide")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="flex gap-2 border-b border-slate-200/60 pb-2 dark:border-white/10 text-xs overflow-x-auto scrollbar-none">
              {quickstartSteps.map((step, idx) => (
                <button
                  key={step.title}
                  type="button"
                  onClick={() => setActiveQuickTab(idx)}
                  className={`rounded-xl px-3.5 py-1.5 font-bold transition whitespace-nowrap ${
                    activeQuickTab === idx
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10"
                  }`}
                >
                  {step.title}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              <p className="text-xs text-slate-600 dark:text-slate-400">
                {quickstartSteps[activeQuickTab].desc}
              </p>

              <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-[#060D1A] font-mono text-xs text-slate-200 shadow-inner">
                <div className="flex items-center justify-between border-b border-slate-800 bg-[#0B1528] px-4 py-2 text-[11px] text-slate-400">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-3.5 w-3.5 text-blue-400" />
                    <span className="font-bold text-slate-300">BASH</span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      handleCopy(quickstartSteps[activeQuickTab].code, activeQuickTab)
                    }
                    className="flex items-center gap-1 rounded-lg bg-white/10 px-2 py-1 text-[10px] text-slate-300 transition hover:bg-white/20"
                  >
                    {copiedIndex === activeQuickTab ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-400" />
                        <span className="text-emerald-400 font-semibold">{t("copiedCode")}</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        <span>{t("copyCode")}</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="overflow-x-auto p-4 leading-relaxed text-cyan-300">
                  <code>{quickstartSteps[activeQuickTab].code}</code>
                </pre>
              </div>
            </div>
          </div>

          {/* 5. Architecture ASCII Diagram */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Boxes className="h-5 w-5 text-blue-600 dark:text-cyan-400" />
                {t("overview.architecture")}
              </h2>
              <button
                type="button"
                onClick={() => onSelectTopic("architecture")}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400"
              >
                <span>{t("overview.viewDetails")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-[#060D1A] p-5 font-mono text-xs text-cyan-300 shadow-inner overflow-x-auto">
              <pre className="leading-tight">
{`┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                  Web User Interface / Giao diện              │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬─────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB │    │  Apache  │  │  MinIO   │
│   │    │(Database│    │  Kafka   │  │ (Storage │
│   │    │ Metadata│    │ (Queue)  │  │ Datasets)│
│   │    └─────────┘    └─────┬────┘  └──────────┘
│   │                         │
│   └─────────────────────────┼─────────────────────┐
│                             │ Task dispatch       │
└─────────────────────────────┼─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │       Workers       │
                   │  (Process Training  │
                   │   Jobs from Kafka)  │
                   └─────────────────────┘`}
              </pre>
            </div>
          </div>

          {/* 6. Releases Summary */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                📋 {t("overview.releases")}
              </h2>
              <button
                type="button"
                onClick={() => onSelectTopic("releases")}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400"
              >
                <span>{t("overview.viewAllReleases")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/60 dark:border-white/10 dark:bg-[#061021]/60">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50/50 text-[11px] font-bold uppercase text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                  <tr>
                    <th className="p-3">{locale === "en" ? "Version" : "Phiên bản"}</th>
                    <th className="p-3">{locale === "en" ? "Date" : "Ngày"}</th>
                    <th className="p-3">{locale === "en" ? "Highlights" : "Đặc điểm chính"}</th>
                    <th className="p-3">{locale === "en" ? "Status" : "Trạng thái"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                  {RELEASES_LIST.map((rel) => (
                    <tr key={rel.version} className="hover:bg-slate-50/50 dark:hover:bg-white/[0.02]">
                      <td className="p-3 font-bold text-blue-600 dark:text-cyan-400 font-mono">
                        {rel.version}
                      </td>
                      <td className="p-3 text-slate-500 dark:text-slate-400">{rel.date}</td>
                      <td className="p-3 text-slate-700 dark:text-slate-300">{rel.description}</td>
                      <td className="p-3">
                        <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${rel.color}`}>
                          {rel.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 7. Contributors Section (from index.md) */}
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-3 dark:border-white/10">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                👥 {t("overview.contributors")}
              </h2>
              <a
                href="https://github.com/optivisionlab/AutoML/graphs/contributors"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400"
              >
                <span>{t("overview.githubContributors")}</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t("overview.contributorsDesc")}
            </p>

            <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[#061021]/70 flex items-center justify-center overflow-x-auto">
              <a
                href="https://github.com/optivisionlab/AutoML/graphs/contributors"
                target="_blank"
                rel="noreferrer"
                className="transition hover:opacity-90"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="https://contrib.rocks/image?repo=optivisionlab/AutoML"
                  alt="HAutoML Contributors"
                  className="max-h-16 rounded-xl"
                />
              </a>
            </div>
          </div>

          {/* 8. Published Paper & Software Citation */}
          <div className="rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 via-indigo-50/40 to-cyan-50/50 p-6 dark:border-blue-900/40 dark:from-blue-950/30 dark:via-indigo-950/20 dark:to-cyan-950/20">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 dark:bg-blue-900/50 dark:text-cyan-300">
                  <Sparkles className="h-3 w-3" />
                  {t("overview.intlPaper")}
                </div>
                <h3 className="mt-2 text-base font-bold text-slate-900 dark:text-white">
                  {t("overview.paperTitle")}
                </h3>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 max-w-2xl leading-relaxed">
                  {t("overview.paperDesc")}
                </p>
              </div>

              <button
                type="button"
                onClick={() => onSelectTopic("citation-license")}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500"
              >
                <span>{t("overview.citation")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
