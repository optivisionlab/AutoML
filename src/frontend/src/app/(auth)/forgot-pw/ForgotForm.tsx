"use client";

import React, { useTransition } from "react";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useToast } from "@/hooks/use-toast";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Label } from "@/components/ui/label";
import styles from "./ForgotForm.module.scss";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { forgotPassword } from "@/app/serverActions/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";

// Schema validate
const forgotSchema = z.object({
  email: z.string().min(1, { message: "Email không được để trống" }).email({
    message: "Email không hợp lệ",
  }),
});

type FormValues = z.infer<typeof forgotSchema>;

const ForgotForm = () => {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  const form = useForm<FormValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: {
      email: "",
    },
  });

  // Submit
  const onSubmit = (data: FormValues) => {
    startTransition(async () => {
      const res = await forgotPassword(data.email);

      if (res.ok) {
        toast({
          title: "Thành công!",
          description: "Đã gửi mật khẩu về gmail của bạn",
          variant: "default",
          style: {
            backgroundColor: "#22c55e", // xanh lá Tailwind green-500
            color: "white",
          },
        });
      } else {
        toast({
          title: "Lỗi",
          description: res.error,
          variant: "destructive",
        });
      }
    });
  };

  return (
    <div className="border border-solid border-[#ddd] p-[45px] rounded-xl">
      <Form {...form}>
        <h1 className="text-2xl text-center text-blue-600 mb-[20px] font-bold">
          Lấy lại mật khẩu
        </h1>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="max-w-md w-full flex flex-col gap-4"
        >
          {/* Email */}
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <Label className="text-center font-bold">
                  Nhập email cần lấy lại
                </Label>
                <FormControl>
                  <Input placeholder="Nhập email..." type="email" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Nút submit */}
          <Button type="submit" disabled={isPending} className="w-full">
            {isPending ? "Đang gửi..." : "Gửi yêu cầu"}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            <div></div>
            <Link
              href="/login"
              className="text-blue-600 hover:underline font-medium"
            >
              Quay về đăng nhập
            </Link>
            <div></div>
            {!isPending && (
              <Link
                href="/change-pw"
                className="text-blue-600 hover:underline font-medium"
              >
                Thay đổi mật khẩu
              </Link>
            )}
          </p>
        </form>
      </Form>
    </div>
  );
};

export default ForgotForm;
