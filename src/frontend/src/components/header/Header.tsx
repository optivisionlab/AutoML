"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { signIn, useSession } from "next-auth/react";
import { Menu, X } from "lucide-react";
import ModeToggle from "@/components/mode-toggle";
import { FaGithub } from "react-icons/fa";
import { useTranslations } from "next-intl";
import LanguageToggle from "@/components/language-toggle";

const landingLinks = [
  { key: "product", href: "/#product" },
  { key: "workflow", href: "/#workflow" },
  { key: "marketplace", href: "/market-place" },
  { key: "docs", href: "/#introduction" },
  { key: "community", href: "/#about-us" },
] as const;

export default function Header() {
  const t = useTranslations("Header");
  const { data: session } = useSession();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-automl-line bg-automl-canvas/92 px-4 py-3 backdrop-blur md:px-6">
      <div className="mx-auto flex h-14 max-w-[1360px] items-center justify-between rounded-2xl border border-automl-line bg-automl-surface/88 px-4 shadow-[0_12px_34px_rgba(15,23,42,0.08)] backdrop-blur dark:shadow-none">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-3"
          prefetch={false}
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white p-1.5 ring-1 ring-automl-line dark:bg-white/10">
            <Image
              src="/logoHautoMLNotext.png"
              alt="HAutoML"
              width={30}
              height={30}
              className="h-7 w-7 object-contain"
              priority
            />
          </span>
          <span>
            <span className="block text-base font-black leading-4 text-automl-ink">
              HAutoML
            </span>
            <span className="text-xs font-semibold text-automl-muted">
              {t("brandSubtitle")}
            </span>
          </span>
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          {landingLinks.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              scroll
              onClick={() => setMobileMenuOpen(false)}
              className="text-sm font-bold text-automl-muted transition hover:text-automl-blue"
            >
              {t(item.key)}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="https://github.com/optivisionlab/AutoML"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden text-automl-muted transition hover:text-automl-ink sm:block"
          >
            <FaGithub className="h-6 w-6" />
          </Link>
          <ModeToggle />
          <LanguageToggle />

          {session ? (
            <Button
              asChild
              className="hidden rounded-xl bg-automl-blue px-5 text-sm font-bold text-white shadow-none hover:bg-automl-blue-hover md:inline-flex"
            >
              <Link href="/dashboard">{t("dashboard")}</Link>
            </Button>
          ) : (
            <div className="hidden items-center space-x-4 md:flex">
              <Button
                onClick={() => signIn()}
                className="rounded-xl bg-automl-surface-muted px-5 text-sm font-bold text-automl-ink shadow-none hover:bg-automl-blue-soft"
              >
                {t("login")}
              </Button>
              <Button
                asChild
                className="rounded-xl bg-automl-blue px-5 text-sm font-bold text-white shadow-none hover:bg-automl-blue-hover"
              >
                <Link href="/register">{t("trial")}</Link>
              </Button>
            </div>
          )}

          <button
            className="ml-2 text-automl-ink md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? t("closeMenu") : t("openMenu")}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="absolute left-4 right-4 top-[78px] z-40 flex flex-col gap-2 rounded-2xl border border-automl-line bg-automl-surface p-4 shadow-xl dark:shadow-none md:hidden">
            {landingLinks.map((item) => (
              <Link
                key={item.key}
                href={item.href}
                className="w-full rounded-xl px-4 py-3 text-sm font-bold text-automl-muted hover:bg-automl-surface-muted hover:text-automl-blue"
                onClick={() => setMobileMenuOpen(false)}
              >
                {t(item.key)}
              </Link>
            ))}

            {session ? (
              <Link href="/dashboard" className="w-full">
                <Button className="w-full rounded-xl bg-automl-blue text-white hover:bg-automl-blue-hover">
                  {t("dashboard")}
                </Button>
              </Link>
            ) : (
              <>
                <Button
                  onClick={() => signIn()}
                  className="w-full rounded-xl bg-automl-surface-muted text-automl-ink hover:bg-automl-blue-soft"
                >
                  {t("login")}
                </Button>

                <Link href="/register" className="w-full">
                  <Button className="w-full rounded-xl bg-automl-blue text-white hover:bg-automl-blue-hover">
                    {t("trial")}
                  </Button>
                </Link>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
