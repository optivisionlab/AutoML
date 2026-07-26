"use client";

import { useEffect, useState } from "react";
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
import { Eye, EyeOff } from "lucide-react";
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { getApiErrorMessage } from "@/redux/api/baseApi";
import { useCreateUserMutation } from "@/redux/api/userApi";

const addUserSchema = z
  .object({
    username: z.string().min(1, "Không được để trống"),
    email: z.string().email("Email không hợp lệ"),
    password: z.string().min(5, "Mật khẩu ít nhất 5 ký tự"),
    confirmPassword: z.string().min(5, "Xác nhận mật khẩu ít nhất 5 ký tự"),
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
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Mật khẩu xác nhận không khớp",
    path: ["confirmPassword"],
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
  const [createUser] = useCreateUserMutation();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [formData, setFormData] = useState<AddUserFormValues | null>(null);

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
    if (!open) reset();
  }, [open, reset]);

  const onSubmit = async (data: AddUserFormValues) => {
    try {
      const submitData = {
        username: data.username,
        email: data.email,
        password: data.password,
        gender: data.gender,
        date: data.date,
        number: data.number,
        fullName: data.fullName,
        role: data.role,
        avatar: data.avatar,
      };

      await createUser(submitData).unwrap();

      toast({
        title: "Thành công!",
        description: "Người dùng mới đã được thêm.",
        className: "bg-green-50 text-green-700",
      });

      reset();
      onClose();
      onSuccess();
    } catch (err) {
      toast({
        title: "Lỗi",
        description: getApiErrorMessage(err, "Không thể thêm người dùng."),
        variant: "destructive",
      });
      console.log(err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="automl-dialog-content max-w-lg">
        <DialogHeader className="automl-dialog-header">
          <DialogTitle className="automl-dialog-title">
            Thêm người dùng mới
          </DialogTitle>
        </DialogHeader>
        <form className="automl-dialog-body automl-dialog-fields">
          <div className="automl-dialog-field">
            <Input
              className="automl-dialog-input"
              placeholder="Username"
              {...register("username")}
            />
            {errors.username && (
              <p className="text-red-500">{errors.username.message}</p>
            )}
          </div>

          <div className="automl-dialog-field">
            <Input
              className="automl-dialog-input"
              placeholder="Họ và tên"
              {...register("fullName")}
            />
            {errors.fullName && (
              <p className="text-red-500">{errors.fullName.message}</p>
            )}
          </div>

          <div className="automl-dialog-field">
            <Input
              className="automl-dialog-input"
              placeholder="Email"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-red-500">{errors.email.message}</p>
            )}
          </div>

          <div className="automl-dialog-field">
            <Input
              className="automl-dialog-input"
              placeholder="Số điện thoại"
              {...register("number")}
            />
            {errors.number && (
              <p className="text-red-500">{errors.number.message}</p>
            )}
          </div>

          {/* Mật khẩu */}
          <div className="automl-dialog-field relative">
            <Input
              className="automl-dialog-input pr-11"
              type={showPassword ? "text" : "password"}
              placeholder="Mật khẩu"
              {...register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              tabIndex={-1}
            >
              {showPassword ? <Eye size={18} /> : <EyeOff size={18} />}
            </button>
            {errors.password && (
              <p className="text-red-500">{errors.password.message}</p>
            )}
          </div>

          {/* Xác nhận mật khẩu */}
          <div className="automl-dialog-field relative">
            <Input
              className="automl-dialog-input pr-11"
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Xác nhận mật khẩu"
              {...register("confirmPassword")}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              tabIndex={-1}
            >
              {showConfirmPassword ? <Eye size={18} /> : <EyeOff size={18} />}
            </button>
            {errors.confirmPassword && (
              <p className="text-red-500">{errors.confirmPassword.message}</p>
            )}
          </div>

          <div className="automl-dialog-field">
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

          <div className="automl-dialog-field">
            <Label>Ngày sinh</Label>
            <Input
              className="automl-dialog-input"
              type="date"
              {...register("date")}
            />
            {errors.date && (
              <p className="text-red-500">{errors.date.message}</p>
            )}
          </div>

          <DialogFooter className="gap-2 pt-2">
            <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  className="automl-action-primary"
                  onClick={handleSubmit((data) => {
                    setFormData(data);
                    setConfirmOpen(true);
                  })}
                  disabled={isSubmitting}
                >
                  Thêm
                </Button>
              </AlertDialogTrigger>

              <AlertDialogContent className="automl-dialog-content max-w-md">
                <AlertDialogHeader className="automl-dialog-header">
                  <AlertDialogTitle className="automl-dialog-title">
                    Bạn có chắc muốn thêm người dùng mới?
                  </AlertDialogTitle>
                </AlertDialogHeader>
                <AlertDialogFooter className="automl-dialog-footer">
                  <AlertDialogCancel className="automl-dialog-button-muted mt-0">
                    Hủy
                  </AlertDialogCancel>
                  <AlertDialogAction
                    className="automl-action-primary"
                    onClick={() => {
                      if (formData) {
                        onSubmit(formData);
                        setConfirmOpen(false);
                      }
                    }}
                  >
                    Xác nhận
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <Button
              type="button"
              variant="secondary"
              className="automl-dialog-button-muted"
              onClick={onClose}
            >
              Hủy
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
