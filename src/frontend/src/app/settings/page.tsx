"use client";

import { useEffect, useState } from "react";
import { Bell, Database, Moon, Palette, ShieldCheck, Sun, Monitor, Zap } from "lucide-react";
import { useTheme } from "next-themes";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

const themeOptions = [
  {
    value: "light",
    labelKey: "theme.light.label",
    descriptionKey: "theme.light.description",
    icon: Sun,
  },
  {
    value: "dark",
    labelKey: "theme.dark.label",
    descriptionKey: "theme.dark.description",
    icon: Moon,
  },
  {
    value: "system",
    labelKey: "theme.system.label",
    descriptionKey: "theme.system.description",
    icon: Monitor,
  },
];

const settingGroups = [
  {
    icon: Bell,
    titleKey: "groups.trainingNotifications.title",
    descriptionKey: "groups.trainingNotifications.description",
    defaultChecked: true,
  },
  {
    icon: Database,
    titleKey: "groups.datasetDraft.title",
    descriptionKey: "groups.datasetDraft.description",
    defaultChecked: true,
  },
  {
    icon: ShieldCheck,
    titleKey: "groups.deployConfirm.title",
    descriptionKey: "groups.deployConfirm.description",
    defaultChecked: true,
  },
  {
    icon: Zap,
    titleKey: "groups.experimental.title",
    descriptionKey: "groups.experimental.description",
    defaultChecked: false,
  },
];

export default function SettingsPage() {
  const t = useTranslations("Settings");
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();
  const [toggles, setToggles] = useState(
    settingGroups.map((item) => item.defaultChecked),
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  const currentTheme = mounted ? theme ?? "system" : "system";

  return (
    <div className="space-y-7">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-automl-blue-soft px-4 py-2 text-sm font-black text-automl-blue">
            <Palette className="h-4 w-4" />
            {t("eyebrow")}
          </div>
          <h1 className="mt-5 text-4xl font-black tracking-tight text-automl-ink dark:text-white lg:text-5xl">
            {t("title")}
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-automl-muted dark:text-white/60">
            {t("subtitle")}
          </p>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
        <article className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
              <Palette className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-black text-automl-ink dark:text-white">
                {t("appearanceTitle")}
              </h2>
              <p className="text-sm font-medium text-automl-muted dark:text-white/55">
                {t("appearanceDescription")}
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {themeOptions.map((option) => {
              const Icon = option.icon;
              const active = currentTheme === option.value;

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTheme(option.value)}
                  className={cn(
                    "rounded-3xl border p-5 text-left transition",
                    active
                      ? "border-automl-blue bg-automl-blue-soft text-automl-blue shadow-sm"
                      : "border-slate-200 bg-slate-50 text-automl-ink hover:border-automl-blue/40 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:text-white",
                  )}
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-automl-blue shadow-sm dark:bg-white/10">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-5 text-lg font-black">{t(option.labelKey)}</h3>
                  <p className="mt-2 text-sm leading-6 text-automl-muted dark:text-white/60">
                    {t(option.descriptionKey)}
                  </p>
                </button>
              );
            })}
          </div>
        </article>

        <article className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/10">
          <h2 className="text-xl font-black text-automl-ink dark:text-white">
            {t("defaultsTitle")}
          </h2>
          <p className="mt-2 text-sm font-medium text-automl-muted dark:text-white/55">
            {t("defaultsDescription")}
          </p>

          <div className="mt-6 space-y-4">
            {settingGroups.map((item, index) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.titleKey}
                  className="flex items-center gap-4 rounded-3xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/5"
                >
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-black text-automl-ink dark:text-white">
                      {t(item.titleKey)}
                    </p>
                    <p className="mt-1 text-sm leading-5 text-automl-muted dark:text-white/55">
                      {t(item.descriptionKey)}
                    </p>
                  </div>
                  <Switch
                    checked={toggles[index]}
                    onCheckedChange={(checked) =>
                      setToggles((current) =>
                        current.map((value, itemIndex) =>
                          itemIndex === index ? checked : value,
                        ),
                      )
                    }
                  />
                </div>
              );
            })}
          </div>
        </article>
      </section>
    </div>
  );
}
