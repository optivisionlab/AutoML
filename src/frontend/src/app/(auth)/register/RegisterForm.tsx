"use client";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import React, { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label } from "@/components/ui/label";
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
import styles from "./RegisterForm.module.scss";
import { useDispatch } from "react-redux";
import { AppDispatch } from "@/redux/store";
import { registerAsync } from "@/redux/slices/registerSlice";
import { useToast } from "@/hooks/use-toast";
import { Eye, EyeOff } from "lucide-react";

const registerSchema = z
  .object({
    username: z
      .string()
      .min(5, {
        message: "Tên đăng nhập phải có ít nhất 5 ký tự",
      })
      .regex(/^\S+$/, {
        message: "Tên đăng nhập không được chứa dấu cách",
      }),
    email: z.string().email({
      message: "Nhập đúng định dạng email",
    }),
    gender: z.string().default("male"),
    date: z.string(),
    number: z
    .string()
    .regex(/^(0[3|5|7|8|9])[0-9]{8}$/, {
      message: "Số điện thoại không hợp lệ",
    }),
    password: z
      .string()
      .min(8, {
        message: "Password phải có ít nhất 8 ký tự",
      })
      .regex(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$/, {
        message: "Password phải có chữ hoa, chữ thường, số và ký tự đặc biệt",
      }),
    passwordConfirm: z.string(),
  })
  .refine(
    (data) => {
      return data.password === data.passwordConfirm;
    },
    {
      message: "Xác nhận mật khẩu sai, vui lòng nhập lại",
      path: ["passwordConfirm"],
    }
  );

const RegisterForm = () => {
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const { toast } = useToast();

  const form = useForm<z.infer<typeof registerSchema>>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      gender: "",
      date: "",
      number: "",
      password: "",
      passwordConfirm: "",
    },
  });
  const dispatch = useDispatch<AppDispatch>();

  const onSubmit = async (values: z.infer<typeof registerSchema>) => {

    const newUser = {
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
      await dispatch(registerAsync(newUser)).unwrap();
      console.log("Đăng ký thành công");

      form.reset();

      toast({
        title: "Đăng ký thành công",
        className: "bg-green-100 text-green-800 border border-green-300",
        description: "Bạn đã đăng ký thành công!"
      });
    } catch (error) {
      toast({
        title: "Đăng ký thất bại",
        description: error.detail || "Lỗi không xác định",
        variant: "destructive",
      });
      console.log("Đăng ký thất bại", error);
    }
  };

  return (
    <div className={styles["register-form"]}>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="max-w-md w-full flex flex-col gap-4 flex-wrap"
        >
          <Label className="text-center text-xl font-bold">Đăng ký</Label>

          <div className="grid grid-cols-2 gap-4">
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormLabel>Tên đăng nhập</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="text"
                        placeholder="Nguyen Van A"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="email"
                        placeholder="nguyenvanA@gmail.com"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />

            <FormField
              control={form.control}
              name="gender"
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormLabel>Giới tính</FormLabel>
                    <FormControl>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value || 'male'}
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue/>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem value="male" defaultValue={"male"}>Nam</SelectItem>
                            <SelectItem value="female">Nữ</SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />

            <FormField
              control={form.control}
              name="date"
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormLabel>Ngày sinh</FormLabel>
                    <FormControl>
                      <Input {...field} type="date" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                );
              }}
            />

            <FormField
              control={form.control}
              name="number"
              render={({ field }) => {
                return (
                  <FormItem>
                    <FormLabel>Số điện thoại</FormLabel>
                    <FormControl>
                      <Input {...field} type="tel" />
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
            <FormField
              control={form.control}
              name="passwordConfirm"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Xác nhận mật khẩu</FormLabel>
                  <FormControl>
                    <div className="relative">
                      <Input
                        {...field}
                        type={showConfirmPassword ? "text" : "password"}
                        placeholder="Confirm password"
                        className="pr-10"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowConfirmPassword(!showConfirmPassword)
                        }
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                        tabIndex={-1}
                      >
                        {showConfirmPassword ? (
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
          </div>
          <Button type="submit" className="w-full">
            Đăng ký
          </Button>
        </form>
      </Form>
    </div>
  );
};

export default RegisterForm;
