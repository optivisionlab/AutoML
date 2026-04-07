"use client";

import React, { useEffect, useTransition } from "react";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useToast } from "@/hooks/use-toast";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { Label } from "@/components/ui/label";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { changePassword } from "@/app/serverActions/auth";
import { useRouter } from "next/navigation";
import Link from "next/link";
import styles from "./ChangepwForm.module.scss";

// Schema validate
const changePwschema = z.object({
  email: z.string().min(1, { message: "Email không được để trống" }),
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
      email: "",
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
        data.email,
        data.password,
        data.new1_password,
        data.new2_password,
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

        router.push("/login");
      } else {
        toast({
          title: "Có lỗi xảy ra",
          description: res.error,
          variant: "destructive",
        });
      }
    });
  };

  useEffect(() => {
    const data = localStorage.getItem("verify-info");
    if (data) {
      const parsed = JSON.parse(data);
      form.setValue("email", parsed.email);
      form.setValue("password", parsed.oldPassword);
    }
  }, [form]);

  return (
    <div className="w-full flex justify-center items-start px-4 sm:px-6 lg:px-8 py-6">
      <div
        className="
      w-full
      max-w-md
      sm:max-w-lg
      md:max-w-xl
      lg:max-w-2xl
      border border-solid border-[#ddd]
      p-5 sm:p-8 md:p-10
      rounded-xl
      bg-white
      shadow-sm
    "
      >
        {/* <div className="border border-solid border-[#ddd] p-[45px] rounded-xl"> */}
        <Form {...form}>
          <h1 className="text-center text-2xl text-blue-600 font-bold">
            Thay đổi mật khẩu
          </h1>

          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="w-full flex flex-col gap-4"
          >
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <Label className="text-center text-sl font-bold">Email</Label>
                  <FormControl>
                    <Input placeholder="Nhập email..." type="text" {...field} />
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
            <Button
              type="submit"
              disabled={isPending}
              className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
            >
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
    </div>
  );
};

export default ChangepwForm;
