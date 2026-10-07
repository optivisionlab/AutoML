"use client";

import React from "react";
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
import { useForgotPasswordMutation } from "@/core/api/authApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import Link from "next/link";
import { useRouter } from "next/navigation";

const forgotSchema = z.object({
  email: z.string().min(1, { message: "Email không được để trống" }).email({
    message: "Email không đúng định dạng",
  }),
});

type FormValues = z.infer<typeof forgotSchema>;

const ForgotForm = () => {
  const { toast } = useToast();
  const router = useRouter();
  const [forgotPassword, { isLoading }] = useForgotPasswordMutation();

  const form = useForm<FormValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: {
      email: "",
    },
  });

  const onSubmit = async (data: FormValues) => {
    try {
      const res = await forgotPassword({ email: data.email }).unwrap();

      toast({
        title: "Đã gửi mã OTP!",
        description:
          res?.message || "Mã OTP 6 số đã được gửi tới email của bạn (hạn 5 phút).",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 4000,
      });

      router.push(`/verify-otp?email=${encodeURIComponent(data.email)}`);
    } catch (err: any) {
      toast({
        title: "Lỗi yêu cầu",
        description: getApiErrorMessage(err, "Không thể gửi mã OTP. Vui lòng kiểm tra lại email."),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="border border-solid border-slate-200 bg-white dark:border-white/10 dark:bg-automl-navy p-[45px] rounded-3xl shadow-sm">
      <Form {...form}>
        <h1 className="text-2xl text-center text-blue-600 dark:text-blue-400 mb-[20px] font-black">
          Quên mật khẩu
        </h1>
        <p className="text-center text-sm text-slate-500 dark:text-slate-400 mb-6">
          Nhập email đã đăng ký để nhận mã OTP xác minh đặt lại mật khẩu mới.
        </p>

        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="max-w-md w-full flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <Label className="font-bold text-slate-900 dark:text-white">
                  Địa chỉ Email
                </Label>
                <FormControl>
                  <Input
                    placeholder="name@example.com"
                    type="email"
                    {...field}
                    className="h-11 rounded-xl"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7] h-11 rounded-xl font-bold"
          >
            {isLoading ? "Đang gửi OTP..." : "Nhận mã OTP"}
          </Button>

          <p className="text-center text-sm text-muted-foreground mt-3">
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
  );
};

export default ForgotForm;
