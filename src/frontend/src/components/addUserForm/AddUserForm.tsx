// components/AddUserForm.tsx
"use client";

import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

const addUserSchema = z.object({
  username: z.string().min(1, "Không được để trống"),
  email: z.string().email("Email không hợp lệ"),
  password: z.string().min(6, "Mật khẩu ít nhất 6 ký tự"),
  gender: z.enum(["male", "female"], {
    required_error: "Vui lòng chọn giới tính",
  }),
  date: z.string().min(1, "Vui lòng chọn ngày sinh"),
  number: z
    .string()
    .min(9, "Số điện thoại không hợp lệ")
    .max(12, "Số điện thoại không hợp lệ"),
  fullName: z.string().min(1, "Không được để trống"),
  role: z.literal("user").default("user"),
  avatar: z.string().optional().default(""),
});

type AddUserFormValues = z.infer<typeof addUserSchema>;

interface AddUserFormProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function AddUserForm({
  open,
  onClose,
  onSuccess,
}: AddUserFormProps) {
  const { toast } = useToast();

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AddUserFormValues>({
    resolver: zodResolver(addUserSchema),
    defaultValues: {
      gender: "female",
      role: "user",
      avatar: "",
    },
  });

  useEffect(() => {
    if (!open) reset(); // reset form khi đóng
  }, [open, reset]);

  const onSubmit = async (data: AddUserFormValues) => {
    try {
      const res = await fetch("http://10.100.200.119:9999/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Thêm người dùng thất bại");
      }

      toast({
        title: "Thành công!",
        description: "Người dùng mới đã được thêm.",
        className: "bg-green-50 text-green-700",
      });

      reset();
      onClose();
      onSuccess();
    } catch (err: any) {
      toast({
        title: "Lỗi",
        description: err.message || "Không thể thêm người dùng.",
        variant: "destructive",
      });
      console.error(err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Thêm người dùng mới</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Input placeholder="Username" {...register("username")} />
            {errors.username && (
              <p className="text-red-500">{errors.username.message}</p>
            )}
          </div>

          <div>
            <Input placeholder="Họ và tên" {...register("fullName")} />
            {errors.fullName && (
              <p className="text-red-500">{errors.fullName.message}</p>
            )}
          </div>

          <div>
            <Input placeholder="Email" {...register("email")} />
            {errors.email && (
              <p className="text-red-500">{errors.email.message}</p>
            )}
          </div>

          <div>
            <Input placeholder="Số điện thoại" {...register("number")} />
            {errors.number && (
              <p className="text-red-500">{errors.number.message}</p>
            )}
          </div>

          <div>
            <Input
              type="password"
              placeholder="Mật khẩu"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-red-500">{errors.password.message}</p>
            )}
          </div>

          <div>
            <Label>Giới tính</Label>
            <Controller
              control={control}
              name="gender"
              render={({ field }) => (
                <RadioGroup onValueChange={field.onChange} value={field.value}>
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="female" id="female" />
                      <Label htmlFor="female">Nữ</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="male" id="male" />
                      <Label htmlFor="male">Nam</Label>
                    </div>
                  </div>
                </RadioGroup>
              )}
            />
            {errors.gender && (
              <p className="text-red-500">{errors.gender.message}</p>
            )}
          </div>

          <div>
            <Label>Ngày sinh</Label>
            <Input type="date" {...register("date")} />
            {errors.date && (
              <p className="text-red-500">{errors.date.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              Thêm
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>
              Hủy
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
