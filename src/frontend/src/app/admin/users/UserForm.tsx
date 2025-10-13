// Form edit users
import { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Button } from "@/components/ui/button";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { User } from "@/hooks/useUsers";

// Use zod validate shema
const formSchema = z.object({
  fullName: z.string().min(5, "Họ và tên có ít nhất 5 ký tự"),
  email: z.string().email("Email không hợp lệ"),
  date: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), "Ngày sinh không hợp lệ"),
  gender: z.enum(["male", "female"], {
    errorMap: () => ({ message: "Giới tính không hợp lệ" }),
  }),
  number: z.string().regex(/^0(3|5|7|8|9)[0-9]{8}$/, {
    message: "Số điện thoại không hợp lệ",
  }),
});

export type FormData = z.infer<typeof formSchema>;

export default function UserForm({
  editingUser,
  onSubmit,
  onClose,
}: {
  editingUser: User | null;
  onSubmit: (data: FormData) => void;
  onClose: () => void;
}) {
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = form;

  useEffect(() => {
    if (editingUser) {
      reset({
        email: editingUser.email,
        fullName: editingUser.fullName,
        gender: editingUser.gender as "male" | "female",
        date: editingUser.date,
        number: editingUser.number,
      });
    }
  }, [editingUser, reset]);

  return (
    <DialogContent>
      <DialogHeader className="flex flex-col items-center text-center">
        <DialogTitle>Chỉnh sửa người dùng</DialogTitle>
      </DialogHeader>

      <form className="grid gap-4 mt-2" onSubmit={handleSubmit(onSubmit)}>
        <div>
          <Label>Email</Label>
          <Input {...register("email")} />
          {errors.email && (
            <p className="text-red-500 text-sm">{errors.email.message}</p>
          )}
        </div>
        <div>
          <Label>Họ tên</Label>
          <Input {...register("fullName")} />
          {errors.fullName && (
            <p className="text-red-500 text-sm">{errors.fullName.message}</p>
          )}
        </div>
        <div>
          <Label>Giới tính</Label>
          <RadioGroup
            className="flex gap-4"
            defaultValue={editingUser?.gender}
            onValueChange={(val) =>
              setValue("gender", val as "male" | "female")
            }
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="male" id="male" />
              <Label htmlFor="male">Nam</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="female" id="female" />
              <Label htmlFor="female">Nữ</Label>
            </div>
          </RadioGroup>
          {errors.gender && (
            <p className="text-red-500 text-sm">{errors.gender.message}</p>
          )}
        </div>
        <div>
          <Label>Ngày sinh</Label>
          <Input type="date" {...register("date")} />
          {errors.date && (
            <p className="text-red-500 text-sm">{errors.date.message}</p>
          )}
        </div>
        <div>
          <Label>Số điện thoại</Label>
          <Input {...register("number")} />
          {errors.number && (
            <p className="text-red-500 text-sm">{errors.number.message}</p>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className=" w-20 text-black px-4 py-2 rounded-md"
          >
            Hủy
          </Button>
          <Button
            type="submit"
            className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
          >
            Lưu
          </Button>
        </div>
      </form>
    </DialogContent>
  );
}
