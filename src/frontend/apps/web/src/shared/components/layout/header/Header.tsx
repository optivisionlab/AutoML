"use client";

import { useEffect, useState } from "react";
import HeaderBrand from "./HeaderBrand";
import HeaderNav from "./HeaderNav";
import HeaderActions from "./HeaderActions";
import HeaderMobileMenu from "./HeaderMobileMenu";
import { cn } from "@/shared/lib/utils";

export default function Header() {
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
    <header className="fixed top-0 inset-x-0 z-50 pointer-events-none bg-transparent transition-all duration-300 px-3 pt-3 pb-2 sm:px-6 md:pt-3.5">
      <div
        className={cn(
          "pointer-events-auto relative mx-auto flex h-14 max-w-[1360px] items-center justify-between rounded-2xl px-3 sm:px-5 transition-all duration-300",
          "border border-white/10 bg-[#0B0F19]/85 text-white shadow-[0_12px_36px_rgba(0,0,0,0.35)] backdrop-blur-xl",
          isScrolled
            ? "border-white/15 bg-[#0B0F19]/95 shadow-[0_18px_45px_rgba(0,0,0,0.55)] ring-1 ring-white/10"
            : ""
        )}
      >
        {/* Brand Logo & Name */}
        <HeaderBrand onNavigate={() => setMobileMenuOpen(false)} />

        {/* Desktop Navigation with Roboflow-style Dropdowns */}
        <HeaderNav />

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
