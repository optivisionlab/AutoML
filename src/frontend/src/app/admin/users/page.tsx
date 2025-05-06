"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pencil, Trash2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

type User = {
  _id: string;
  username: string;
  email: string;
  password: string;
  gender: string;
  date: string;
  number: string;
  role: string;
  fullName: string;
};

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

type FormData = z.infer<typeof formSchema>;

const UserManagementPage = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const { setValue } = useForm<FormData>({
    resolver: zodResolver(formSchema),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
  });

  const fetchUsers = async () => {
    try {
      const res = await fetch("http://127.0.0.1:9999/users");
      const data = await res.json();
      setUsers(data);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleEdit = (user: User) => {
    setEditingUser(user);
    reset({
      fullName: user.fullName,
      email: user.email,
      gender: user.gender as "male" | "female",
      date: user.date,
      number: user.number,
    });
    setIsDialogOpen(true);
  };

  const handleDelete = async (id: string) => {
    console.log("Delete:", id);
  };

  const handleDialogClose = () => {
    setEditingUser(null);
    setIsDialogOpen(false);
  };

  const onSubmit = async (data: FormData) => {
    console.log("Submit:", data);
    if (!editingUser) return;

    try {
      const res = await fetch(
        `http://127.0.0.1:9999/update/${editingUser.username}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(data),
        }
      );

      if (!res.ok) throw new Error("Failed to update user");

      await fetchUsers(); // refresh list
      handleDialogClose();
    } catch (error) {
      console.error("Update error:", error);
    }
  };

  console.log("editingUser", editingUser);

  return (
    <div className="p-6">
      <Card className="shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold text-[#3b6cf5]">
            Quản lý tài khoản người dùng
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Họ tên</TableHead>
                <TableHead>Mật khẩu</TableHead>
                <TableHead>Giới tính</TableHead>
                <TableHead>Ngày sinh</TableHead>
                <TableHead>SĐT</TableHead>
                <TableHead>Chức năng</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user._id}>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{user.fullName}</TableCell>
                  <TableCell>{user.password}</TableCell>
                  <TableCell>{user.gender}</TableCell>
                  <TableCell>{user.date}</TableCell>
                  <TableCell>{user.number}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEdit(user)}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDelete(user._id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
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
                <p className="text-red-500 text-sm">
                  {errors.fullName.message}
                </p>
              )}
            </div>
            <div>
              <Label>Giới tính</Label>
              <RadioGroup
                className="flex gap-4"
                defaultValue={editingUser?.gender}
                onValueChange={(val) => {
                  setValue("gender", val as "male" | "female");
                }}
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
                onClick={handleDialogClose}
              >
                Hủy
              </Button>
              <Button type="submit">Lưu</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UserManagementPage;