"use client";

import { useEffect, useState } from "react";
import { BookOpen, Search, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

import HeaderBrand from "@/shared/components/layout/header/HeaderBrand";
import HeaderActions from "@/shared/components/layout/header/HeaderActions";
import HeaderMobileMenu from "@/shared/components/layout/header/HeaderMobileMenu";
import { cn } from "@/shared/lib/utils";

type DocsHeaderProps = {
  onOpenSearch: () => void;
  onToggleMobileSidebar: () => void;
  isMobileSidebarOpen: boolean;
};

export default function DocsHeader({
  onOpenSearch,
  onToggleMobileSidebar,
  isMobileSidebarOpen,
}: DocsHeaderProps) {
  const t = useTranslations("Docs");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 15);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header className="sticky top-0 z-50 w-full pointer-events-none bg-transparent transition-all duration-300 px-3 pt-3 pb-2 sm:px-6 md:pt-3.5">
      <div
        className={cn(
          "pointer-events-auto relative mx-auto flex h-14 max-w-[1360px] items-center justify-between rounded-2xl px-3 sm:px-5 transition-all duration-300",
          "border border-white/10 bg-[#0B0F19]/85 text-white shadow-[0_12px_36px_rgba(0,0,0,0.35)] backdrop-blur-xl",
          isScrolled
            ? "border-white/15 bg-[#0B0F19]/95 shadow-[0_18px_45px_rgba(0,0,0,0.55)] ring-1 ring-white/10"
            : ""
        )}
      >
        {/* Left: Brand Logo & Docs Tag */}
        <div className="flex items-center gap-2.5">
          {/* Mobile docs sidebar toggle */}
          <button
            type="button"
            onClick={onToggleMobileSidebar}
            aria-label="Toggle documentation navigation"
            aria-expanded={isMobileSidebarOpen}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white lg:hidden",
              isMobileSidebarOpen && "border-blue-500/50 bg-blue-500/20 text-white"
            )}
            title={t("tableOfContents")}
          >
            <BookOpen className="h-4 w-4 text-blue-400" />
          </button>

          <HeaderBrand onNavigate={() => setMobileMenuOpen(false)} />

          <span className="hidden sm:inline-flex items-center gap-1 rounded-lg border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[11px] font-bold text-blue-400 backdrop-blur">
            <Sparkles className="h-3 w-3" />
            Docs
          </span>
        </div>

        {/* Center: Search Bar replacing the old navigation links */}
        <div className="flex flex-1 items-center justify-center max-w-md px-2 sm:px-4">
          <button
            type="button"
            onClick={onOpenSearch}
            className="group flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 backdrop-blur transition-all duration-200 hover:border-blue-400/50 hover:bg-white/10 hover:shadow-[0_0_20px_rgba(37,99,255,0.15)]"
          >
            <div className="flex items-center gap-2 truncate">
              <Search className="h-3.5 w-3.5 text-blue-400 transition-colors group-hover:text-cyan-300" />
              <span className="truncate text-slate-400 group-hover:text-slate-200">
                {t("searchPlaceholder")}
              </span>
            </div>
            <kbd className="hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-white/15 bg-white/10 px-1.5 text-[10px] font-medium text-slate-300">
              <span>⌘</span>K
            </kbd>
          </button>
        </div>

        {/* Right actions: GitHub, ModeToggle, LanguageToggle, Auth CTA, Mobile Hamburger */}
        <HeaderActions
          mobileMenuOpen={mobileMenuOpen}
          onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)}
        />

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <HeaderMobileMenu onClose={() => setMobileMenuOpen(false)} />
        )}
      </div>
    </header>
  );
}
