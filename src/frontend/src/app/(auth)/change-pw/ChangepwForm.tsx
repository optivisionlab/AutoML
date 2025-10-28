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
import styles from "./ChangepwForm.module.scss";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { changePassword, forgotPassword } from "@/app/serverActions/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";

// Schema validate
const changePwschema = z.object({
  username: z.string().min(1, { message: "Tên không được để trống" }),
  password: z.string().min(1, { message: "Password không được để trống" }),
  new1_password: z.string().min(1, { message: "Password không được để trống" }),
  new2_password: z.string().min(1, { message: "Password không được để trống" }),
});

type FormValues = z.infer<typeof changePwschema>;

const ChangepwForm = () => {
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  const form = useForm<FormValues>({
    resolver: zodResolver(changePwschema),
    defaultValues: {
      username: "",
      password: "",
      new1_password: "",
      new2_password: "",
    },
  });

  // Submit
  const onSubmit = (data: FormValues) => {
    console.log(data);
    startTransition(async () => {
      const res = await changePassword(
        data.username,
        data.password,
        data.new1_password,
        data.new2_password
      );

      console.log(res);

      if (res.ok) {
        toast({
          title: "Thành công!",
          description: res.noError || "Thay đổi mật khẩu thành công",
          variant: "default",
          style: {
            backgroundColor: "#22c55e",
            color: "white",
          },
        });
      } else {
        toast({
          title: "Có lỗi xảy ra",
          description: res.error,
          variant: "destructive",
        });
      }
    });
  };

  return (
    <div className="border border-solid border-[#ddd] p-[45px] rounded-xl">
      <Form {...form}>
        <h1 className="text-center text-2xl text-blue-600 font-bold">
          Thay đổi mật khẩu
        </h1>

        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="max-w-md w-full flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => (
              <FormItem>
                <Label className="text-center text-sl font-bold">
                  Tên đăng nhập
                </Label>
                <FormControl>
                  <Input placeholder="Nhập tên..." type="text" {...field} />
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
                <Label className="text-center text-sl font-bold">
                  Mật khẩu cũ
                </Label>
                <FormControl>
                  <Input
                    placeholder="Nhập mật khẩu cũ..."
                    type="password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="new1_password"
            render={({ field }) => (
              <FormItem>
                <Label className="text-center text-sl font-bold">
                  Mật khẩu mới
                </Label>
                <FormControl>
                  <Input
                    placeholder="Nhập mật khẩu mới..."
                    type="password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="new2_password"
            render={({ field }) => (
              <FormItem>
                <Label className="text-center text-sl font-bold">
                  Xác nhận mật khẩu mới
                </Label>
                <FormControl>
                  <Input
                    placeholder="Nhập lại mật khẩu mới..."
                    type="password"
                    {...field}
                  />
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

export default ChangepwForm;
