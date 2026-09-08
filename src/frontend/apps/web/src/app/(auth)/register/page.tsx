"use client";

import Link from "next/link";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import RegisterForm from "@/features/auth/components/register/RegisterForm";
import AppLoading from "@/shared/components/common/AppLoading";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import { useTranslations } from "next-intl";

const RegisterPage = () => {
  const t = useTranslations("Auth.registerPage");
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
      <div className="grid min-h-svh lg:grid-cols-[1.1fr_0.9fr]">
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

            <BreadcrumbNav items={[{ label: "Đăng ký" }]} />
          </div>

          <div className="flex flex-1 items-center justify-center">
            <div className="w-full max-w-3xl">
              <RegisterForm />
            </div>
          </div>
        </section>

        <section className="relative hidden overflow-hidden bg-automl-navy p-10 lg:flex lg:items-center lg:justify-center">
          <div className="absolute inset-0 opacity-80 [background:radial-gradient(circle_at_18%_22%,rgba(255,126,77,0.24),transparent_26%),radial-gradient(circle_at_78%_20%,rgba(47,96,255,0.28),transparent_32%),linear-gradient(135deg,#10131f,#171d2d)]" />
          <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/10 p-6 text-white shadow-lg shadow-black/20">
            <span className="inline-flex rounded-full bg-white/10 px-4 py-2 text-xs font-bold text-white/80">
              {t("badge")}
            </span>
            <h2 className="mt-6 text-3xl font-black tracking-tight">
              {t("title")}
            </h2>
            <p className="mt-4 text-sm leading-6 text-white/70">
              {t("body")}
            </p>

            <div className="mt-8 space-y-3">
              <AuthStep index="1" title={t("steps.create.title")} body={t("steps.create.body")} />
              <AuthStep index="2" title={t("steps.verify.title")} body={t("steps.verify.body")} />
              <AuthStep index="3" title={t("steps.workflow.title")} body={t("steps.workflow.body")} />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
};

const AuthStep = ({ index, title, body }: { index: string; title: string; body: string }) => {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/10 p-4">
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-automl-blue text-sm font-black text-white">
          {index}
        </div>
        <div>
          <p className="font-bold text-white">{title}</p>
          <p className="mt-1 text-sm leading-5 text-white/60">{body}</p>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
