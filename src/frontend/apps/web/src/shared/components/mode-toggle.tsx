"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/shared/components/ui/button";
import { useTranslations } from "next-intl";

import { cn } from "@/shared/lib/utils";

export function ModeToggle({ className }: { className?: string }) {
  const t = useTranslations("Common");
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "relative h-10 w-10 rounded-xl border-slate-200/80 bg-white shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:hover:bg-white/15 transition-colors",
        className
      )}
      aria-label={isDark ? t("switchToLight") : t("switchToDark")}
    >
      <Sun className="h-4.5 w-4.5 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
      <Moon className="absolute h-4.5 w-4.5 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
    </Button>
  );
}

export default ModeToggle;
