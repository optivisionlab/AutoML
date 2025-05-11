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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useToast } from "@/hooks/use-toast";
import AddUserForm from "@/components/addUserForm/AddUserForm";
import { Plus } from "lucide-react";

// Types
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

// Form Component
const UserForm = ({
  editingUser,
  onSubmit,
  onClose,
}: {
  editingUser: User | null;
  onSubmit: (data: FormData) => void;
  onClose: () => void;
}) => {
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
};

// Main Page Component
const UserManagementPage = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [pendingFormData, setPendingFormData] = useState<FormData | null>(null);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { toast } = useToast();

  const fetchUsers = async () => {
    try {
      const res = await fetch("http://10.100.200.119:9999/users");
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
    setIsDialogOpen(true);
  };

  const handleDelete = (user: User) => {
    setUserToDelete(user);
    setIsDeleteDialogOpen(true);
  };

  const handleDialogClose = () => {
    setEditingUser(null);
    setIsDialogOpen(false);
  };

  const onSubmit = (data: FormData) => {
    setPendingFormData(data);
    setIsConfirmDialogOpen(true);
  };

  const handleConfirmUpdate = async () => {
    if (!editingUser || !pendingFormData) return;

    try {
      const res = await fetch(
        `http://10.100.200.119:9999/update/${editingUser.username}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(pendingFormData),
        }
      );

      if (!res.ok) {
        toast({
          title: "Cập nhật thất bại",
          description: "Đã xảy ra lỗi khi cập nhật.",
          variant: "destructive",
          duration: 3000,
        });
        throw new Error("Failed to update user");
      }

      toast({
        title: "Cập nhật thành công!",
        description: "Thông tin người dùng đã được cập nhật.",
        className:
          "bg-green-50 border border-green-300 text-green-700 [&>div>h3]:text-lg [&>div>h3]:font-semibold",
        duration: 3000,
      });

      await fetchUsers();
      setIsConfirmDialogOpen(false);
      handleDialogClose();
    } catch (error) {
      console.log("Update error:", error);
    }
  };

  const handleConfirmDelete = async () => {
    if (!userToDelete) return;

    try {
      const res = await fetch(
        `http://10.100.200.119:9999/delete/${userToDelete.username}`,
        {
          method: "DELETE",
        }
      );

      if (!res.ok) {
        toast({
          title: "Xóa thất bại",
          description: "Đã xảy ra lỗi khi xóa người dùng.",
          variant: "destructive",
          duration: 3000,
        });
        throw new Error("Failed to delete user");
      }

      toast({
        title: "Xóa thành công!",
        description: `Người dùng ${userToDelete.username} đã được xóa.`,
        className:
          "bg-green-50 border border-green-300 text-green-700 [&>div>h3]:text-lg [&>div>h3]:font-semibold",
        duration: 3000,
      });

      await fetchUsers(); // refresh list
    } catch (error) {
      console.error("Delete error:", error);
    } finally {
      setIsDeleteDialogOpen(false);
      setUserToDelete(null);
    }
  };

  return (
    <div className="p-6">
      <Card className="shadow-lg">
        <CardHeader className="px-4">
          <CardTitle className="text-2xl font-bold text-[#3b6cf5] text-center w-full">
            Quản lý tài khoản người dùng
          </CardTitle>
          <div className="flex justify-end w-full mt-2">
            <Button
              onClick={() => setIsAddDialogOpen(true)}
              className="flex gap-2 bg-blue-500 text-white px-3 py-2 text-sm hover:bg-blue-600"
            >
              <span className="w-5 h-5 rounded-full bg-white text-blue-500 flex items-center justify-center">
                <Plus size={14} />
              </span>
              Thêm mới
            </Button>
          </div>
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
                  <TableCell>{user.gender === "male" ? "Nam" : "Nữ"}</TableCell>
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
                        onClick={() => handleDelete(user)}
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
        <UserForm
          editingUser={editingUser}
          onSubmit={onSubmit}
          onClose={handleDialogClose}
        />
      </Dialog>

      {/* Confirmation Dialog */}
      <AlertDialog
        open={isConfirmDialogOpen}
        onOpenChange={setIsConfirmDialogOpen}
      >
        <AlertDialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white shadow-xl p-6 rounded-xl w-full max-w-md">
          <AlertDialogHeader className="text-center space-y-2">
            <AlertDialogTitle className="text-xl font-semibold text-center">
              XÁC NHẬN
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-600 text-center">
              Bạn có chắc chắn muốn cập nhật thông tin người dùng này không?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className=" flex !justify-center gap-4">
            <AlertDialogCancel
              onClick={() => setIsConfirmDialogOpen(false)}
              className="bg-red-600 w-20 text-white hover:bg-red-500 hover:text-white px-4 py-2 rounded-md"
            >
              Hủy
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmUpdate}
              className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
            >
              Cập nhật
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <AlertDialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white shadow-xl p-6 rounded-xl w-full max-w-md">
          <AlertDialogHeader className="text-center space-y-2">
            <AlertDialogTitle className="text-xl font-semibold text-center">
              XÁC NHẬN XOÁ
            </AlertDialogTitle>
            <AlertDialogDescription className="text-gray-600 text-center">
              {`Bạn có chắc chắn muốn xóa người dùng ${userToDelete?.username}?`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex !justify-center gap-4">
            <AlertDialogCancel
              onClick={() => setIsDeleteDialogOpen(false)}
              className="bg-gray-300 w-20 text-black hover:bg-gray-400 px-4 py-2 rounded-md"
            >
              Hủy
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-red-600 w-20 text-white hover:bg-red-500 px-4 py-2 rounded-md"
            >
              Xoá
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AddUserForm
        open={isAddDialogOpen}
        onClose={() => setIsAddDialogOpen(false)}
        onSuccess={() => fetchUsers()}
      />
    </div>
  );
};

export default UserManagementPage;
