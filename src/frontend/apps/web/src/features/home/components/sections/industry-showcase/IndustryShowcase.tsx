"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  Award,
  Maximize2,
  Trophy,
  Users,
  X,
  Zap,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useLanguage } from "@/core/i18n/LanguageProvider";
import {
  AWARDS_DATA,
  INDUSTRY_ROW_1,
  INDUSTRY_ROW_2,
  type IndustryCard,
  type AwardItem,
} from "./industry-showcase-config";

export default function IndustryShowcase() {
  const t = useTranslations("Home.industryShowcase");
  const { locale } = useLanguage();
  const isEn = locale === "en";
  const [previewAward, setPreviewAward] = useState<AwardItem | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreviewAward(null);
    };
    if (previewAward) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [previewAward]);

  const getAwardIcon = (type: AwardItem["iconType"]) => {
    switch (type) {
      case "trophy":
        return <Trophy className="h-4 w-4 text-amber-500 dark:text-amber-400" />;
      case "award":
        return <Award className="h-4 w-4 text-purple-500 dark:text-purple-400" />;
      case "users":
        return <Users className="h-4 w-4 text-cyan-500 dark:text-cyan-400" />;
      case "zap":
        return <Zap className="h-4 w-4 text-blue-500 dark:text-blue-400" />;
    }
  };

  const renderCard = (card: IndustryCard, index: number) => {
    return (
      <div
        key={`${card.id}-${index}`}
        className="group relative h-[185px] w-[290px] shrink-0 overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-100 shadow-sm transition-all duration-300 hover:scale-[1.03] hover:shadow-xl dark:border-white/10 dark:bg-slate-900 sm:h-[210px] sm:w-[335px] cursor-pointer"
      >
        <Image
          src={card.image}
          alt="HAutoML Achievement"
          fill
          sizes="(max-width: 640px) 290px, 335px"
          className="object-cover transition-transform duration-500 group-hover:scale-105"
        />
      </div>
    );
  };

  return (
    <section
      id="industry-achievements"
      className="relative w-full overflow-hidden bg-white dark:bg-[#020817] py-16 text-automl-ink transition-colors sm:py-24"
    >
      {/* Background Ambient Glows */}
      <div className="pointer-events-none absolute -top-40 right-1/4 h-[500px] w-[500px] rounded-full bg-purple-600/10 blur-[130px] dark:bg-purple-600/15" />
      <div className="pointer-events-none absolute bottom-0 left-1/4 h-[450px] w-[450px] rounded-full bg-blue-600/10 blur-[120px] dark:bg-blue-600/15" />

      <div className="mx-auto max-w-[1360px] px-4 sm:px-6 lg:px-8">
        {/* Header Block with Colorful Highlight */}
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3.5">
            <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl lg:text-5xl dark:text-white">
              {t("headingPrefix")}{" "}
              <span className="bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-500 bg-clip-text text-transparent dark:from-purple-400 dark:via-indigo-400 dark:to-cyan-300">
                {t("headingHighlight")}
              </span>{" "}
              {t("headingSuffix")}
            </h2>

            <p className="text-base font-semibold leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
              {t("description")}
            </p>
          </div>

          <div className="shrink-0">
            <Link
              href="/team"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-xs font-bold text-slate-900 shadow-sm transition-all duration-200 hover:border-slate-400 hover:bg-slate-50 dark:border-white/15 dark:bg-white/10 dark:text-white dark:hover:bg-white/15 active:scale-95"
            >
              <span>{t("exploreUseCases")}</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        {/* 5 Awards Cards Row matching image_gt */}
        <div className="mt-10 grid grid-cols-1 gap-3.5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 sm:gap-4">
          {AWARDS_DATA.map((award) => (
            <div
              key={award.id}
              onClick={() => setPreviewAward(award)}
              className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-3.5 shadow-sm transition-all duration-200 hover:border-blue-400/50 hover:shadow-lg dark:border-white/10 dark:bg-white/[0.03] backdrop-blur-sm cursor-pointer hover:-translate-y-1"
            >
              <div>
                {/* Image Thumbnail with zoom effect */}
                <div className="relative h-36 w-full overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800">
                  <Image
                    src={award.image}
                    alt={isEn ? award.titleEn : award.title}
                    fill
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 20vw"
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-center p-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-black/60 backdrop-blur-xs px-2.5 py-1 text-[10px] font-bold text-white border border-white/20">
                      <Maximize2 className="h-3 w-3" /> {isEn ? "View Photo" : "Xem ảnh phóng to"}
                    </span>
                  </div>
                </div>

                {/* Badge & Icon Bar */}
                <div className="flex items-center justify-between mt-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 ring-1 ring-slate-200 dark:bg-white/10 dark:ring-white/10">
                    {getAwardIcon(award.iconType)}
                  </div>
                  <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[10px] font-extrabold text-blue-600 dark:text-cyan-300 border border-blue-500/20">
                    {isEn ? (award.badgeEn || award.badge) : award.badge}
                  </span>
                </div>

                {/* Award Title (Taken from image name) */}
                <h3 className="mt-2.5 text-xs sm:text-sm font-bold tracking-tight text-slate-900 dark:text-white line-clamp-2 leading-snug">
                  {isEn ? award.titleEn : award.title}
                </h3>
              </div>

              {/* Award Subtitle */}
              <p className="mt-2 text-[11px] font-semibold leading-normal text-slate-500 dark:text-slate-400 line-clamp-2">
                {isEn ? award.subtitleEn : award.subtitle}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Dual-Row Infinite Scrolling Carousel (Marquee theo mẫu Roboflow) */}
      <div className="relative mt-12 space-y-4 overflow-hidden">
        {/* Left & Right Smooth Edge Fade Out Masks */}
        <div className="pointer-events-none absolute inset-y-0 left-0 z-20 w-16 bg-gradient-to-r from-white to-transparent dark:from-[#020817] sm:w-36" />
        <div className="pointer-events-none absolute inset-y-0 right-0 z-20 w-16 bg-gradient-to-l from-white to-transparent dark:from-[#020817] sm:w-36" />

        {/* ROW 1: Cuộn từ phải sang trái */}
        <div className="flex overflow-hidden">
          <div className="animate-marquee flex gap-4 pause-hover">
            {INDUSTRY_ROW_1.map((card, i) => renderCard(card, i))}
            {INDUSTRY_ROW_1.map((card, i) => renderCard(card, i + 100))}
          </div>
        </div>

        {/* ROW 2: Cuộn ngược lại từ trái sang phải */}
        <div className="flex overflow-hidden">
          <div className="animate-marquee-reverse flex gap-4 pause-hover">
            {INDUSTRY_ROW_2.map((card, i) => renderCard(card, i))}
            {INDUSTRY_ROW_2.map((card, i) => renderCard(card, i + 100))}
          </div>
        </div>
      </div>

      {/* Lightbox Modal for Award Photo Preview */}
      {previewAward && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setPreviewAward(null)}
        >
          <div
            className="relative flex flex-col max-w-4xl w-full max-h-[90vh] rounded-2xl bg-white dark:bg-slate-900 overflow-hidden shadow-2xl border border-slate-200 dark:border-white/10"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 dark:border-white/10">
              <div className="flex items-center gap-2.5 min-w-0 pr-4">
                <span className="shrink-0 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-extrabold text-blue-600 dark:text-cyan-300 border border-blue-500/20">
                  {isEn ? (previewAward.badgeEn || previewAward.badge) : previewAward.badge}
                </span>
                <h4 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white truncate">
                  {isEn ? previewAward.titleEn : previewAward.title}
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setPreviewAward(null)}
                className="shrink-0 rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-white transition"
                aria-label="Đóng"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* High-res Image Preview */}
            <div className="relative w-full h-[55vh] sm:h-[65vh] bg-black/95">
              <Image
                src={previewAward.image}
                alt={isEn ? previewAward.titleEn : previewAward.title}
                fill
                className="object-contain"
                sizes="(max-width: 1200px) 100vw, 1000px"
                priority
              />
            </div>

            {/* Modal Footer Subtitle */}
            <div className="px-5 py-3 bg-slate-50 dark:bg-slate-950 border-t border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 text-center font-semibold">
              {isEn ? previewAward.subtitleEn : previewAward.subtitle}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
