"use client";
import React, { useState } from "react";
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
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { signIn } from "next-auth/react";
import styles from "./LoginForm.module.scss";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";

// schema để validate form
const loginSchema = z.object({
  username: z.string().min(3, {
    message: "Tên đăng nhập phải có ít nhất 3 ký tự",
  }),
  password: z.string().min(5, {
    message: "Mật khẩu phải có ít nhất 5 ký tự",
  }),
});

const LoginForm = () => {
  const [showPassword, setShowPassword] = useState(false);
  const { toast } = useToast();
  const router = useRouter();

  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const onSubmit = async (values: z.infer<typeof loginSchema>) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const res = await signIn("credentials", {
      username: values.username,
      password: values.password,
      redirect: false,
      callbackUrl: "/",
    });

    if (res?.ok && !res.error) {
      toast({
        title: "Đăng nhập thành công",
        className: "bg-green-100 text-green-800 border border-green-300",
        duration: 3000,
      });
      setTimeout(() => {
        router.push("/");
      }, 100);
    } else {
      toast({
        title: "Đăng nhập thất bại",
        description: "Tên đăng nhập hoặc mật khẩu không đúng.",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  return (
    <div className={styles["login-form"]}>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="max-w-md w-full flex flex-col gap-4"
        >
          <Label className="text-center text-xl font-bold">Đăng nhập</Label>
          <FormField
            control={form.control}
            name="username"
            render={({ field }) => {
              return (
                <FormItem>
                  <FormLabel>Tên đăng nhập</FormLabel>
                  <FormControl>
                    <Input {...field} type="text" placeholder="nguyenvana" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              );
            }}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Mật khẩu</FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      {...field}
                      type={showPassword ? "text" : "password"}
                      placeholder="Password"
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                      tabIndex={-1}
                    >
                      {showPassword ? (
                        <Eye className="w-5 h-5" />
                      ) : (
                        <EyeOff className="w-5 h-5" />
                      )}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <p className="text-center text-sm text-muted-foreground">
            Chưa có tài khoản?{" "}
            <Link
              href="/register"
              className="text-blue-600 hover:underline font-medium"
            >
              Đăng ký
            </Link>
          </p>

          <Button
            type="submit"
            className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
          >
            Đăng nhập
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            <Link
              href="/forgot-pw"
              className="text-blue-600 hover:underline font-medium"
            >
              Bạn quên mật khẩu?
            </Link>
          </p>
        </form>
      </Form>
    </div>
  );
};

export default LoginForm;
