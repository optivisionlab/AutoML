"use client";

import { use, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";

import { useToast } from "@/hooks/use-toast";
import AddUserForm from "@/components/addUserForm/AddUserForm";
import { Plus } from "lucide-react";
import UserTable from "./UserTable";

import UserForm from "./UserForm";
import { User } from "@/hooks/useUsers";
import useUsers from "@/hooks/useUsers";
import DialogForm from "../../../components/dialog";

// Main Page Component
const UserManagementPage = () => {
  // const [users, setUsers] = useState<User[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [pendingFormData, setPendingFormData] = useState<FormData | null>(null);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { users, fetchUsers } = useUsers();
  const { toast } = useToast();

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
        `${process.env.NEXT_PUBLIC_BASE_API}/update/${editingUser.username}`,
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
        `${process.env.NEXT_PUBLIC_BASE_API}/delete/${userToDelete.username}`,
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
          <UserTable
            users={users}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
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
      {/* Dialog Confirm  */}
      <DialogForm
        open={isConfirmDialogOpen}
        onOpenChange={setIsConfirmDialogOpen}
        title="XÁC NHẬN"
        description="Bạn có chắc chắn muốn cập nhật thông tin người dùng này không?"
        canceltext="Hủy"
        actionText="Cập nhật"
        onCancle={() => setIsConfirmDialogOpen(false)}
        onConfirm={handleConfirmUpdate}
      />

      {/* Dialog delete */}
      <DialogForm
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        title="XÁC NHẬN XOÁ"
        description={`Bạn có chắc chắn muốn xóa người dùng ${userToDelete?.username}?`}
        canceltext="Hủy"
        actionText="Xoá"
        onCancle={() => setIsDeleteDialogOpen(false)}
        onConfirm={handleConfirmDelete}
      />
      <AddUserForm
        open={isAddDialogOpen}
        onClose={() => setIsAddDialogOpen(false)}
        onSuccess={() => fetchUsers()}
      />
    </div>
  );
};

export default UserManagementPage;
