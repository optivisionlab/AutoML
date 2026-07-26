"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRegisterUserMutation } from "@/redux/api/authApi";
import { useToast } from "@/hooks/use-toast";
import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";

type RegisterFormValues = {
  fullName: string;
  username: string;
  email: string;
  gender: string;
  date: string;
  number: string;
  password: string;
  passwordConfirm: string;
};

const inputClass =
  "h-11 rounded-xl border-automl-line bg-automl-surface-muted text-automl-ink shadow-none placeholder:text-automl-muted focus:border-automl-blue focus:bg-automl-surface focus:ring-4 focus:ring-automl-blue/10";

const RegisterForm = () => {
  const t = useTranslations("Auth.register");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const { toast } = useToast();
  const router = useRouter();
  const registerSchema = useMemo(
    () =>
      z
        .object({
          fullName: z.string().min(5, {
            message: t("validation.fullNameMin"),
          }),
          username: z
            .string()
            .min(5, {
              message: t("validation.usernameMin"),
            })
            .regex(/^\S+$/, {
              message: t("validation.usernameNoSpaces"),
            }),
          email: z.string().email({
            message: t("validation.email"),
          }),
          gender: z.string().default("male"),
          date: z.string(),
          number: z.string().regex(/^0(3|5|7|8|9)[0-9]{8}$/, {
            message: t("validation.phone"),
          }),
          password: z
            .string()
            .min(8, {
              message: t("validation.passwordMin"),
            })
            .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$/, {
              message: t("validation.passwordComplex"),
            }),
          passwordConfirm: z.string(),
        })
        .refine((data) => data.password === data.passwordConfirm, {
          message: t("validation.passwordConfirm"),
          path: ["passwordConfirm"],
        }),
    [t],
  );

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      fullName: "",
      username: "",
      email: "",
      gender: "male",
      date: "",
      number: "",
      password: "",
      passwordConfirm: "",
    },
  });

  const [registerUser, { isLoading }] = useRegisterUserMutation();

  const onSubmit = async (values: RegisterFormValues) => {
    const newUser = {
      fullName: values.fullName,
      username: values.username,
      email: values.email,
      password: values.password,
      gender: values.gender,
      date: values.date,
      number: values.number,
      role: "user",
      avatar: "",
    };

    try {
      await registerUser(newUser).unwrap();
      form.reset();
      router.push(`/verify-email?email=${values.email}`);
    } catch (error) {
      const message =
        typeof error === "object" && error !== null && "data" in error
          ? (error.data as { detail?: string })?.detail
          : undefined;

      toast({
        title: t("toast.failed"),
        description: message || t("toast.unknownError"),
        variant: "destructive",
      });
      console.log("Register failed", error);
    }
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

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="fullName"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("fullName")}</FormLabel>
                <FormControl>
                  <Input {...field} type="text" placeholder={t("fullNamePlaceholder")} className={inputClass} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("username")}</FormLabel>
                <FormControl>
                  <Input {...field} type="text" placeholder="nguyenvana" autoComplete="username" className={inputClass} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("email")}</FormLabel>
                <FormControl>
                  <Input {...field} type="email" placeholder="name@example.com" autoComplete="email" className={inputClass} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="gender"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("gender")}</FormLabel>
                <FormControl>
                  <Select onValueChange={field.onChange} value={field.value ?? "male"}>
                    <SelectTrigger className={inputClass}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="border-automl-line bg-automl-surface text-automl-ink">
                      <SelectGroup>
                        <SelectItem value="male">{t("male")}</SelectItem>
                        <SelectItem value="female">{t("female")}</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="date"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("birthDate")}</FormLabel>
                <FormControl>
                  <Input {...field} type="date" className={inputClass} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="number"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("phone")}</FormLabel>
                <FormControl>
                  <Input {...field} type="tel" placeholder="0912345678" autoComplete="tel" className={inputClass} />
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
                <FormLabel className="font-bold text-automl-ink">{t("password")}</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      {...field}
                      type={showPassword ? "text" : "password"}
                      placeholder={t("passwordPlaceholder")}
                      autoComplete="new-password"
                      className={`${inputClass} pr-11`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-automl-muted transition hover:text-automl-ink"
                      tabIndex={-1}
                      aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                    >
                      {showPassword ? <Eye className="h-5 w-5" /> : <EyeOff className="h-5 w-5" />}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="passwordConfirm"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="font-bold text-automl-ink">{t("confirmPassword")}</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      {...field}
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder={t("confirmPasswordPlaceholder")}
                      autoComplete="new-password"
                      className={`${inputClass} pr-11`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-automl-muted transition hover:text-automl-ink"
                      tabIndex={-1}
                      aria-label={showConfirmPassword ? t("hideConfirmPassword") : t("showConfirmPassword")}
                    >
                      {showConfirmPassword ? <Eye className="h-5 w-5" /> : <EyeOff className="h-5 w-5" />}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <Button
          type="submit"
          disabled={isLoading}
          className="h-11 w-full rounded-xl bg-automl-blue font-bold text-white shadow-sm hover:bg-automl-blue-hover"
        >
          {isLoading ? t("submitting") : t("submit")}
        </Button>

        <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-automl-line">
          <span className="relative z-10 bg-automl-surface px-3 text-automl-muted">
            {t("or")}
          </span>
        </div>

        <Button
          type="button"
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
          {t("hasAccount")}{" "}
          <Link href="/login" className="font-bold text-automl-blue underline-offset-4 hover:underline">
            {t("login")}
          </Link>
        </p>
      </form>
    </Form>
  );
};

export default RegisterForm;
