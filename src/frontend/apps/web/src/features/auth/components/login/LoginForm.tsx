"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import * as z from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { useToast } from "@/shared/hooks/use-toast";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

type LoginFormValues = {
  username: string;
  password: string;
};

const authInputClass =
  "h-11 rounded-xl border-automl-line bg-automl-surface-muted text-automl-ink shadow-none placeholder:text-automl-muted focus:border-automl-blue focus:bg-automl-surface focus:ring-4 focus:ring-automl-blue/10";

const LoginForm = () => {
  const t = useTranslations("Auth.login");
  const [showPassword, setShowPassword] = useState(false);
  const { toast } = useToast();
  const router = useRouter();
  const loginSchema = useMemo(
    () =>
      z.object({
        username: z.string().min(3, {
          message: t("validation.usernameMin"),
        }),
        password: z.string().min(5, {
          message: t("validation.passwordMin"),
        }),
      }),
    [t],
  );

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    const res = await signIn("credentials", {
      username: values.username,
      password: values.password,
      redirect: false,
      callbackUrl: "/",
    });

    if (res?.ok && res.error == null) {
      toast({
        title: t("toast.success"),
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      setTimeout(() => {
        router.push("/");
      }, 100);
    } else {
      toast({
        title: t("toast.failed"),
        description: t("toast.failedDescription"),
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = `${process.env.NEXT_PUBLIC_BASE_API}/google/login`;
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-6 rounded-3xl border border-automl-line bg-automl-surface p-7 shadow-[0_24px_70px_rgba(15,23,42,0.12)] dark:shadow-none sm:p-8"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-automl-line bg-white p-2 shadow-sm dark:bg-white/10">
            <Image
              src="/logoHautoMLNotext.png"
              alt="HAutoML"
              width={40}
              height={40}
              className="h-10 w-10 object-contain"
              priority
            />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-black tracking-tight text-automl-ink">
              {t("title")}
            </h1>
            <p className="text-balance text-sm text-automl-muted">
              {t("subtitle")}
            </p>
          </div>
        </div>

        <div className="grid gap-5">
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("username")}</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    type="text"
                    placeholder="nguyenvana"
                    autoComplete="username"
                    className={authInputClass}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center">
                  <FormLabel className="font-bold text-automl-ink">{t("password")}</FormLabel>
                  <Link
                    href="/forgot-pw"
                    className="ml-auto text-sm font-semibold text-automl-blue underline-offset-4 hover:underline"
                  >
                    {t("forgotPassword")}
                  </Link>
                </div>
                <FormControl>
                  <div className="relative">
                    <Input
                      {...field}
                      type={showPassword ? "text" : "password"}
                      placeholder={t("passwordPlaceholder")}
                      autoComplete="current-password"
                      className={`${authInputClass} pr-11`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-automl-muted transition hover:text-automl-ink"
                      tabIndex={-1}
                      aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                    >
                      {showPassword ? (
                        <Eye className="h-5 w-5" />
                      ) : (
                        <EyeOff className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button
            type="submit"
            disabled={form.formState.isSubmitting}
            className="h-11 w-full rounded-xl bg-automl-blue font-bold text-white shadow-sm hover:bg-automl-blue-hover"
          >
            {form.formState.isSubmitting ? t("submitting") : t("submit")}
          </Button>

          <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-automl-line">
            <span className="relative z-10 bg-automl-surface px-3 text-automl-muted">
              {t("continueWith")}
            </span>
          </div>

          <Button
            type="button"
            onClick={handleGoogleLogin}
            variant="outline"
            className="h-11 w-full rounded-xl border-automl-line bg-automl-surface font-bold text-automl-ink shadow-none hover:bg-automl-surface-muted"
          >
            <svg viewBox="0 0 24 24" className="mr-2 h-5 w-5" aria-hidden="true">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
            </svg>
            {t("google")}
          </Button>

          <p className="text-center text-sm text-automl-muted">
            {t("noAccount")}{" "}
            <Link
              href="/register"
              className="font-bold text-automl-blue underline-offset-4 hover:underline"
            >
              {t("register")}
            </Link>
          </p>
        </div>
      </form>
    </Form>
  );
};

export default LoginForm;
