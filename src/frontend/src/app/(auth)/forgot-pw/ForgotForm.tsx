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
  const router = useRouter();
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
      console.log(data.email);
      const res = await forgotPassword(data.email);

      if (res.ok) {
        toast({
          title: "Thành công!",
          description: "Đã gửi mật khẩu về gmail của bạn",
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
    <div className={styles["forgot-form"]}>
      <Form {...form}>
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
                <Label className="text-center text-xl font-bold">
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
            <Link
              href="/login"
              className="text-blue-600 hover:underline font-medium"
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
