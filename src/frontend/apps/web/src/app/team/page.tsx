"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  ExternalLink,
  Github,
  Globe,
  MapPin,
} from "lucide-react";

import MemberLab from "@/features/home/components/sections/member-lab/MemberLab";
import { LAB_INFO } from "@/features/docs/data/docs-content";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import { useTranslations } from "next-intl";

export default function TeamPage() {
  const t = useTranslations("Team");

  return (
    <div className="relative min-h-screen bg-slate-50/70 text-slate-900 transition-colors dark:bg-[#020817] dark:text-slate-100 overflow-x-hidden pt-24 sm:pt-28">
      {/* Background ambient glows matching HAutoML design */}
      <div className="pointer-events-none absolute -top-40 right-10 h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] dark:bg-blue-500/15" />
      <div className="pointer-events-none absolute top-[500px] -left-20 h-[450px] w-[450px] rounded-full bg-cyan-500/10 blur-[100px] dark:bg-cyan-500/10" />

      {/* Main Page Container aligned with Header (max-w-[1360px] mx-auto px-3 sm:px-6) */}
      <div className="mx-auto max-w-[1360px] px-3 sm:px-6 space-y-12 pb-24">
        {/* 1. Hero Header */}
        <div className="space-y-4 pt-2 sm:pt-4">
          <BreadcrumbNav items={[{ label: t("breadcrumb") }]} />

          <h1 className="text-3xl font-black tracking-tight text-slate-900 sm:text-5xl dark:text-white">
            {t("title")}
          </h1>

          <p className="max-w-4xl text-base font-medium leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
            {t("description")}
          </p>
        </div>

        {/* 2. OptiVisionLab Overview Profile Card */}
        <div className="rounded-3xl border border-blue-200/80 bg-gradient-to-br from-blue-50/80 via-white/80 to-cyan-50/50 p-6 sm:p-8 backdrop-blur-xl shadow-sm dark:border-blue-900/40 dark:from-blue-950/30 dark:via-[#061021]/80 dark:to-cyan-950/20">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3 max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3 py-1 text-xs font-bold text-white shadow-sm">
                  <Building2 className="h-3.5 w-3.5" />
                  {LAB_INFO.name}
                </span>
                <span className="rounded-xl bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                  HaUI SICT University
                </span>
                <span className="rounded-xl bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Open-Source AI Lab
                </span>
              </div>

              <h2 className="text-xl font-black text-slate-900 sm:text-2xl dark:text-white">
                {LAB_INFO.institution}
              </h2>

              <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                {LAB_INFO.mission}
              </p>

              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400 pt-1">
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5 text-blue-500" />
                  {LAB_INFO.address}
                </span>
              </div>
            </div>

            <div className="flex shrink-0 flex-wrap gap-2.5 sm:flex-col">
              <a
                href={LAB_INFO.website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
              >
                <Globe className="h-4 w-4 text-blue-500" />
                <span>{t("labWebsite")}</span>
                <ExternalLink className="h-3 w-3 text-slate-400" />
              </a>

              <a
                href={LAB_INFO.github}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-slate-800 dark:bg-white/10 dark:hover:bg-white/20"
              >
                <Github className="h-4 w-4" />
                <span>{t("githubRepo")}</span>
                <ExternalLink className="h-3 w-3 text-slate-400" />
              </a>

              <Link
                href="/docs"
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-blue-500"
              >
                <span>{t("readDocs")}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>

        {/* 3. Full Modern MemberLab Component */}
        <MemberLab />
      </div>
    </div>
  );
}
