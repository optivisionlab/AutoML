"use client";

import React, { useEffect, useState } from "react";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useToast } from "@/shared/hooks/use-toast";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/shared/components/ui/form";
import { Label } from "@/shared/components/ui/label";
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { useResetPasswordMutation } from "@/core/api/authApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";

const changePwSchema = z
  .object({
    new_password: z.string().min(6, { message: "Mật khẩu phải có ít nhất 6 ký tự" }),
    confirm_password: z.string().min(6, { message: "Mật khẩu phải có ít nhất 6 ký tự" }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Mật khẩu xác nhận không khớp",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof changePwSchema>;

const ChangepwForm = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [resetPassword, { isLoading }] = useResetPasswordMutation();
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [token, setToken] = useState<string>("");

  useEffect(() => {
    const urlToken = searchParams?.get("token");
    const storedToken =
      typeof window !== "undefined"
        ? sessionStorage.getItem("reset_token")
        : null;

    const effectiveToken = urlToken || storedToken || "";
    setToken(effectiveToken);
  }, [searchParams]);

  const form = useForm<FormValues>({
    resolver: zodResolver(changePwSchema),
    defaultValues: {
      new_password: "",
      confirm_password: "",
    },
  });

  const onSubmit = async (data: FormValues) => {
    if (!token) {
      toast({
        title: "Thiếu mã xác thực",
        description:
          "Không tìm thấy mã xác thực đặt lại mật khẩu. Vui lòng thực hiện lại từ bước quên mật khẩu.",
        variant: "destructive",
      });
      return;
    }

    try {
      await resetPassword({
        token,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      }).unwrap();

      sessionStorage.removeItem("reset_token");

      toast({
        title: "Thành công!",
        description:
          "Cập nhật mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 4000,
      });

      router.push("/login");
    } catch (err: any) {
      toast({
        title: "Đặt lại mật khẩu thất bại",
        description: getApiErrorMessage(
          err,
          "Mã xác thực đã hết hạn hoặc dữ liệu không hợp lệ.",
        ),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="w-full flex justify-center items-start px-4 sm:px-6 lg:px-8 py-6">
      <div className="w-full max-w-md border border-slate-200 dark:border-white/10 p-6 sm:p-8 rounded-3xl bg-white dark:bg-automl-navy shadow-sm">
        <Form {...form}>
          <h1 className="text-center text-2xl text-blue-600 dark:text-blue-400 font-black mb-2">
            Đặt lại mật khẩu mới
          </h1>
          <p className="text-center text-xs text-slate-500 dark:text-slate-400 mb-6">
            Nhập mật khẩu mới an toàn cho tài khoản của bạn
          </p>

          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="w-full flex flex-col gap-4"
          >
            <FormField
              control={form.control}
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <Label className="font-bold text-slate-900 dark:text-white">
                    Mật khẩu mới
                  </Label>
                  <FormControl>
                    <div className="relative">
                      <Input
                        placeholder="Nhập mật khẩu mới..."
                        type={showNewPassword ? "text" : "password"}
                        {...field}
                        className="h-11 rounded-xl pr-11"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        tabIndex={-1}
                      >
                        {showNewPassword ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="confirm_password"
              render={({ field }) => (
                <FormItem>
                  <Label className="font-bold text-slate-900 dark:text-white">
                    Xác nhận mật khẩu mới
                  </Label>
                  <FormControl>
                    <div className="relative">
                      <Input
                        placeholder="Nhập lại mật khẩu mới..."
                        type={showConfirmPassword ? "text" : "password"}
                        {...field}
                        className="h-11 rounded-xl pr-11"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        tabIndex={-1}
                      >
                        {showConfirmPassword ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
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
              disabled={isLoading}
              className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7] h-11 rounded-xl font-bold mt-2"
            >
              {isLoading ? "Đang cập nhật..." : "Cập nhật mật khẩu"}
            </Button>

            <p className="text-center text-sm text-muted-foreground mt-2">
              <Link
                href="/login"
                className="text-blue-600 dark:text-blue-400 hover:underline font-semibold"
              >
                Quay về đăng nhập
              </Link>
            </p>
          </form>
        </Form>
      </div>
    </div>
  );
};

export default ChangepwForm;
