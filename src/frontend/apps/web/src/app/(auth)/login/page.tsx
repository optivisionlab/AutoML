"use client";

import Link from "next/link";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LoginForm from "@/features/auth/components/login/LoginForm";
import AppLoading from "@/shared/components/common/AppLoading";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import { useTranslations } from "next-intl";

const LoginPage = () => {
  const t = useTranslations("Auth.loginPage");
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/");
    }
  }, [router, status]);

  if (status === "loading") {
    return <AppLoading variant="page" label={t("loading")} />;
  }

  return (
    <main className="min-h-svh bg-slate-50 text-automl-ink dark:bg-[#070A13]">
      <div className="grid min-h-svh lg:grid-cols-[0.95fr_1.05fr]">
        <section className="flex flex-col gap-8 px-6 py-8 md:px-10 lg:px-14">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Link href="/" className="flex items-center gap-3 text-sm font-black text-automl-ink hover:opacity-90 transition">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-automl-line bg-automl-surface p-1.5">
                <Image
                  src="/logoHautoMLNotext.png"
                  alt="HAutoML"
                  width={30}
                  height={30}
                  className="h-7 w-7 object-contain"
                  priority
                />
              </div>
              <div className="leading-tight">
                <p>HAutoML</p>
                <p className="text-xs font-semibold text-automl-muted">Open AutoML</p>
              </div>
            </Link>

            <BreadcrumbNav items={[{ label: "Đăng nhập" }]} />
          </div>

          <div className="flex flex-1 items-center justify-center">
            <div className="w-full max-w-md">
              <LoginForm />
            </div>
          </div>
        </section>

        <AuthVisualPanel />
      </div>
    </main>
  );
};

const AuthVisualPanel = () => {
  const t = useTranslations("Auth.loginPage.visual");

  return (
    <section className="relative hidden overflow-hidden bg-automl-navy p-10 lg:flex lg:items-center lg:justify-center">
      <div className="absolute inset-0 opacity-80 [background:radial-gradient(circle_at_22%_18%,rgba(255,126,77,0.22),transparent_28%),radial-gradient(circle_at_80%_26%,rgba(47,96,255,0.28),transparent_32%),linear-gradient(135deg,#10131f,#171d2d)]" />
      <div className="relative w-full max-w-xl rounded-2xl border border-white/10 bg-white/10 p-6 shadow-lg shadow-black/20">
        <div className="mb-8 flex items-center justify-between gap-6">
          <div>
            <p className="text-sm font-semibold text-white/60">{t("eyebrow")}</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight text-white">
              {t("title")}
            </h2>
          </div>
          <span className="shrink-0 rounded-full bg-automl-blue px-4 py-2 text-xs font-bold text-white">
            {t("badge")}
          </span>
        </div>

        <div className="relative min-h-[340px] rounded-2xl border border-slate-200 bg-[#f7f9fc] p-8 text-automl-ink">
          <div className="absolute left-24 top-24 h-1 w-28 rounded-full bg-cyan-400" />
          <div className="absolute left-[12.4rem] top-[8.8rem] h-24 w-1 rounded-full bg-cyan-500" />
          <div className="absolute left-[18rem] top-[10rem] h-1 w-24 rounded-full bg-amber-400" />
          <div className="absolute right-24 top-[8.4rem] h-24 w-1 rounded-full bg-automl-blue" />

          <WorkflowNode className="left-10 top-10" icon="DS" title={t("dataset")} body="CSV/Excel + metadata" tone="cyan" />
          <WorkflowNode className="left-10 top-48" icon="FE" title={t("preprocess")} body={t("preprocessBody")} tone="orange" />
          <WorkflowNode className="right-8 top-24" icon="AI" title={t("autoTrain")} body={t("autoTrainBody")} tone="blue" />
          <WorkflowNode className="bottom-8 right-8" icon="EV" title={t("evaluate")} body={t("evaluateBody")} tone="green" />

          <div className="absolute bottom-8 left-10 w-56 rounded-2xl bg-automl-ink p-4 text-white shadow-md">
            <p className="text-xs text-white/50">{t("bestModel")}</p>
            <div className="mt-1 flex items-end justify-between gap-4">
              <p className="font-black">KNeighborsClassifier</p>
              <p className="text-xl font-black text-automl-green">92%</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

const WorkflowNode = ({
  className,
  icon,
  title,
  body,
  tone,
}: {
  className: string;
  icon: string;
  title: string;
  body: string;
  tone: "cyan" | "orange" | "blue" | "green";
}) => {
  const toneClass = {
    cyan: "bg-automl-cyan-soft text-cyan-600",
    orange: "bg-automl-orange-soft text-automl-orange",
    blue: "bg-automl-blue-soft text-automl-blue",
    green: "bg-automl-green-soft text-automl-green",
  }[tone];

  return (
    <div className={`absolute w-44 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl text-xs font-black ${toneClass}`}>
        {icon}
      </div>
      <p className="font-black">{title}</p>
      <p className="text-xs text-automl-muted">{body}</p>
    </div>
  );
};

export default LoginPage;
