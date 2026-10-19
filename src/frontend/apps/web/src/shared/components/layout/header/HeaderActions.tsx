"use client";

import Link from "next/link";
import { signIn, useSession } from "next-auth/react";
import { FaGithub } from "react-icons/fa";
import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/shared/components/ui/button";
import ModeToggle from "@/shared/components/mode-toggle";
import LanguageToggle from "@/shared/components/language-toggle";

interface HeaderActionsProps {
  mobileMenuOpen: boolean;
  onToggleMobileMenu: () => void;
}

export default function HeaderActions({
  mobileMenuOpen,
  onToggleMobileMenu,
}: HeaderActionsProps) {
  const t = useTranslations("Header");
  const { data: session } = useSession();

  return (
    <div className="flex items-center gap-1.5 sm:gap-2">
      {/* GitHub Repository */}
      <Link
        href="https://github.com/optivisionlab/AutoML"
        target="_blank"
        rel="noopener noreferrer"
        className="hidden rounded-xl p-2 text-slate-300 transition-colors hover:bg-white/10 hover:text-white sm:flex"
        aria-label="GitHub Repository"
      >
        <FaGithub className="h-5 w-5" />
      </Link>

      {/* Mode & Language Toggles */}
      <ModeToggle className="h-9 w-9 rounded-xl border-white/10 bg-white/5 text-white hover:bg-white/10 hover:text-white" />
      <LanguageToggle className="h-9 px-2.5 rounded-xl border-white/10 bg-white/5 text-white hover:bg-white/10 hover:text-white" />

      {/* Auth / Dashboard CTA */}
      {session ? (
        <Button
          asChild
          className="hidden h-9 rounded-xl bg-blue-600 px-4 text-xs font-bold text-white shadow-[0_0_20px_rgba(37,99,255,0.35)] transition-all duration-200 hover:bg-blue-500 lg:inline-flex"
        >
          <Link href="/dashboard">{t("dashboard")}</Link>
        </Button>
      ) : (
        <div className="hidden items-center gap-2 lg:flex">
          <Button
            onClick={() => signIn()}
            className="h-9 rounded-xl border border-white/10 bg-white/5 px-3.5 text-xs font-bold text-white shadow-none transition-all duration-150 hover:bg-white/15"
          >
            {t("login")}
          </Button>
          <Button
            asChild
            className="h-9 rounded-xl bg-blue-600 px-4 text-xs font-bold text-white shadow-[0_0_20px_rgba(37,99,255,0.35)] transition-all duration-200 hover:bg-blue-500"
          >
            <Link href="/register">{t("trial")}</Link>
          </Button>
        </div>
      )}

      {/* Mobile Menu Hamburger */}
      <button
        type="button"
        className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-white transition-colors hover:bg-white/15 lg:hidden"
        onClick={onToggleMobileMenu}
        aria-label={mobileMenuOpen ? t("closeMenu") : t("openMenu")}
      >
        {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
    </div>
  );
}
