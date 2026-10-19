"use client";

import React from "react";
import { FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";

export default function IntroductionSection() {
  const t = useTranslations("Home");

  return (
    <section
      id="introduction"
      className="relative w-full overflow-hidden bg-white dark:bg-[#020817] py-14 sm:py-20 text-automl-ink transition-colors"
    >
      {/* Ánh sáng ambient kết nối êm ái giữa Hero 3D và Giới thiệu */}
      <div className="pointer-events-none absolute -top-20 left-1/2 -translate-x-1/2 h-44 w-[750px] rounded-full bg-blue-500/10 blur-[110px] dark:bg-blue-600/15" />

      {/* Đường hairline mờ dần 2 đầu tạo sự chuyển tiếp tinh tế */}
      <div className="pointer-events-none absolute top-0 inset-x-0 flex justify-center">
        <div className="h-[1px] w-full max-w-4xl bg-gradient-to-r from-transparent via-blue-500/25 via-cyan-400/20 to-transparent" />
      </div>

      <div className="mx-auto max-w-[1360px] px-4 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-slate-200/90 bg-gradient-to-br from-slate-50/90 via-white to-blue-50/40 p-6 sm:p-10 shadow-sm backdrop-blur-xl dark:border-white/10 dark:from-[#0B1120] dark:via-[#0D1527] dark:to-[#090E1A] dark:shadow-2xl">
          {/* Ambient inner glow */}
          <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-cyan-500/10 blur-3xl dark:bg-cyan-500/15" />

          <div className="relative grid gap-8 lg:grid-cols-12 lg:items-center lg:gap-12">
            {/* Cột trái: Tiêu đề + Đơn vị nghiên cứu */}
            <div className="space-y-4 lg:col-span-5">
              <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl lg:text-4xl dark:text-white">
                {t("introTitle")}
              </h2>

              <div className="flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-cyan-400">
                <FlaskConical className="h-4 w-4 text-blue-600 dark:text-cyan-400 shrink-0" />
                <span>{t("introInstitution")}</span>
              </div>
            </div>

            {/* Cột phải: Đoạn văn giới thiệu ngắn & highlight */}
            <div className="space-y-4 lg:col-span-7">
              <p className="text-base font-semibold leading-relaxed text-slate-700 dark:text-slate-200 sm:text-lg">
                {t("introBodyPrefix")}{" "}
                <span className="inline-block rounded-lg bg-blue-500/10 px-2 py-0.5 font-black text-blue-600 dark:bg-blue-500/20 dark:text-cyan-300">
                  HYPER-PROCESSOR AUTOMATED MACHINE LEARNING
                </span>
                . {t("introBodySuffix")}
              </p>

              <p className="text-sm font-semibold leading-relaxed text-slate-600 dark:text-slate-300 sm:text-base">
                {t("introLowCode")}
              </p>

              {/* Feature Chips */}
              <div className="flex flex-wrap gap-2 pt-2">
                <span className="rounded-full border border-slate-200 bg-slate-100/80 px-3.5 py-1 text-xs font-bold text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                  {t("introChipLowCode")}
                </span>
                <span className="rounded-full border border-slate-200 bg-slate-100/80 px-3.5 py-1 text-xs font-bold text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                  {t("introChipResearch")}
                </span>
                <span className="rounded-full border border-slate-200 bg-slate-100/80 px-3.5 py-1 text-xs font-bold text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                  {t("introChipAutoML")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
