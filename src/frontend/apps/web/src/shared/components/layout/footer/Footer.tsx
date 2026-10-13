"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowUp,
  ExternalLink,
  Mail,
  MapPin,
  Star,
  BookOpen,
} from "lucide-react";
import { FaFacebook, FaGithub, FaYoutube } from "react-icons/fa";
import { useTranslations } from "next-intl";
import {
  footerNavigationColumns,
  footerSocialLinks,
  footerLabInfo,
} from "./footer-config";

export default function Footer() {
  const t = useTranslations("Footer");

  const scrollToTop = () => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const getSocialIcon = (key: string) => {
    switch (key) {
      case "github":
        return <FaGithub className="h-4 w-4" />;
      case "facebook":
        return <FaFacebook className="h-4 w-4" />;
      case "youtube":
        return <FaYoutube className="h-4 w-4" />;
      default:
        return null;
    }
  };

  return (
    <footer
      id="contact"
      className="relative z-10 w-full overflow-hidden border-t border-white/10 bg-[#070A13] text-white transition-colors"
    >
      {/* Ambient background glows */}
      <div className="pointer-events-none absolute -top-24 left-1/2 h-72 w-[800px] -translate-x-1/2 rounded-full bg-blue-600/10 blur-[130px]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-64 w-64 rounded-full bg-cyan-600/5 blur-[100px]" />

      {/* Top subtle highlight gradient line */}
      <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-blue-500/40 via-cyan-400/40 to-transparent" />

      <div className="relative mx-auto max-w-[1360px] px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        {/* Modern Lab & Project Callout Banner */}
        <div className="mb-12 rounded-2xl border border-white/10 bg-gradient-to-r from-white/[0.04] via-blue-950/20 to-white/[0.02] p-6 backdrop-blur-xl sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <h3 className="text-xl font-black tracking-tight sm:text-2xl">
                {t("ctaTitle")}
              </h3>
              <p className="max-w-2xl text-sm leading-relaxed text-slate-300">
                {t("ctaSubtitle")}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <a
                href={footerLabInfo.githubRepo}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/10 px-4 py-2.5 text-xs font-bold text-white shadow-sm transition-all duration-200 hover:scale-[1.02] hover:bg-white/15 hover:border-white/25 active:scale-[0.98]"
              >
                <Star className="h-4 w-4 text-amber-400 fill-amber-400" />
                <span>{t("starGitHub")}</span>
              </a>
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-[0_0_20px_rgba(37,99,255,0.35)] transition-all duration-200 hover:scale-[1.02] hover:bg-blue-500 active:scale-[0.98]"
              >
                <BookOpen className="h-4 w-4" />
                <span>{t("exploreDocs")}</span>
              </Link>
            </div>
          </div>
        </div>

        {/* Main Footer Content Grid */}
        <div className="grid gap-10 lg:grid-cols-12 lg:gap-8">
          {/* Brand & Lab Information (5 cols) */}
          <div className="space-y-6 lg:col-span-4 xl:col-span-5">
            <Link
              href="/"
              className="group inline-flex items-center gap-3 transition-opacity hover:opacity-90"
            >
              <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 p-1.5 ring-1 ring-white/15 backdrop-blur transition-all duration-200 group-hover:scale-105 group-hover:bg-white/15 group-hover:ring-blue-400/40">
                <Image
                  src="/logoHautoMLNotext.png"
                  alt="HAutoML"
                  width={32}
                  height={32}
                  className="h-8 w-8 object-contain drop-shadow-[0_2px_10px_rgba(37,99,255,0.5)]"
                />
              </div>
              <div>
                <span className="block text-lg font-black leading-none tracking-tight text-white transition-colors group-hover:text-blue-200">
                  HAutoML
                </span>
                <span className="text-xs font-semibold text-slate-400">
                  {t("brandSubtitle")}
                </span>
              </div>
            </Link>

            {/* Live Operational Status */}
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span>{t("systemOperational")}</span>
            </div>

            <p className="max-w-md text-sm leading-relaxed text-slate-300">
              {t("description")}
            </p>

            {/* Contact & Location Details */}
            <div className="space-y-2.5 text-xs text-slate-300">
              <p className="flex items-start gap-2.5">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
                <span className="leading-relaxed">{t("address")}</span>
              </p>
              <p className="flex items-center gap-2.5">
                <Mail className="h-4 w-4 shrink-0 text-cyan-400" />
                <a
                  href={`mailto:${footerLabInfo.email}`}
                  className="font-semibold text-slate-300 transition-colors hover:text-white hover:underline"
                >
                  {footerLabInfo.email}
                </a>
              </p>
            </div>

            {/* Social Icons */}
            <div className="flex items-center gap-2 pt-2">
              {footerSocialLinks.map((item) => (
                <a
                  key={item.key}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={item.name}
                  className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 transition-all duration-200 hover:scale-110 hover:border-white/25 hover:bg-white/15 hover:text-white"
                >
                  {getSocialIcon(item.key)}
                </a>
              ))}
            </div>
          </div>

          {/* Navigation Links Grid (7 cols) */}
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:col-span-8 xl:col-span-7">
            {footerNavigationColumns.map((column) => (
              <div key={column.id} className="space-y-4">
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">
                  {t(column.titleKey)}
                </h4>
                <ul className="space-y-2.5 text-xs font-medium">
                  {column.items.map((item) => {
                    const content = (
                      <span className="group flex items-center gap-1.5 transition-colors hover:text-white">
                        <span className="text-slate-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-white">
                          {t(item.labelKey)}
                        </span>
                        {item.badge && (
                          <span className="rounded-md border border-blue-500/20 bg-blue-500/15 px-1.5 py-0.5 text-[9px] font-bold text-blue-300">
                            {item.badge}
                          </span>
                        )}
                        {item.external && (
                          <ExternalLink className="h-3 w-3 text-slate-500 transition-colors group-hover:text-slate-300" />
                        )}
                      </span>
                    );

                    return (
                      <li key={item.key}>
                        {item.external ? (
                          <a
                            href={item.href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block"
                          >
                            {content}
                          </a>
                        ) : (
                          <Link href={item.href} className="inline-block">
                            {content}
                          </Link>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom Bar: Copyright & Back To Top */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-8 sm:flex-row">
          <div className="flex flex-col items-center gap-1 text-center text-xs text-slate-400 sm:items-start sm:text-left">
            <p>{t("copyright")}</p>
            <p className="text-[11px] text-slate-500">{t("license")}</p>
          </div>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={scrollToTop}
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-300 backdrop-blur transition-all duration-200 hover:border-white/20 hover:bg-white/10 hover:text-white active:scale-95"
              aria-label={t("backToTop")}
            >
              <ArrowUp className="h-3.5 w-3.5" />
              <span>{t("backToTop")}</span>
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
