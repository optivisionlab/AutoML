"use client";

import AppLoading from "@/shared/components/common/AppLoading";
import { useState } from "react";
import { Button } from "@/shared/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/shared/components/ui/card";
import { Dialog } from "@/shared/components/ui/dialog";
import { useToast } from "@/shared/hooks/use-toast";
import AddUserForm from "@/features/account/components/user-form/AddUserForm";
import { Plus } from "lucide-react";
import UserTable from "@/features/account/components/admin-users/UserTable";
import UserForm, { FormData as UserFormData } from "@/features/account/components/admin-users/UserForm";
import useUsers from "@/features/account/hooks/useUsers";
import DialogForm from "@/shared/components/DialogForm";
import {
  User,
  useDeleteUserMutation,
  useUpdateUserMutation,
} from "@/core/api/userApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import PaginationCustom from "@/shared/components/common/Panigation";

const UserManagementPage = () => {
  const [currentPage, setCurrentPage] = useState(1);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [pendingFormData, setPendingFormData] = useState<UserFormData | null>(null);
  const [isConfirmDialogOpen, setIsConfirmDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const { users, meta, fetchUsers, isLoading } = useUsers({ page: currentPage, page_size: 10 });
  const [updateUser] = useUpdateUserMutation();
  const [deleteUser] = useDeleteUserMutation();
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

  const onSubmit = (data: UserFormData) => {
    setPendingFormData(data);
    setIsConfirmDialogOpen(true);
  };

  const handleConfirmUpdate = async () => {
    if (!editingUser || !pendingFormData) return;
    const targetId = editingUser._id || editingUser.username;

    try {
      await updateUser({
        id: targetId,
        data: pendingFormData,
      }).unwrap();

      toast({
        title: "Cập nhật thành công!",
        description: "Thông tin người dùng đã được cập nhật.",
        className:
          "bg-green-50 border border-green-300 text-green-700 font-semibold",
        duration: 3000,
      });

      await fetchUsers();
      setIsConfirmDialogOpen(false);
      handleDialogClose();
    } catch (error) {
      toast({
        title: "Cập nhật thất bại",
        description: getApiErrorMessage(error, "Đã xảy ra lỗi khi cập nhật."),
        variant: "destructive",
        duration: 3000,
      });
      console.log("Update error:", error);
    }
  };

  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    const targetId = userToDelete._id || userToDelete.username;

    try {
      await deleteUser(targetId).unwrap();

      toast({
        title: "Xóa thành công!",
        description: `Người dùng ${userToDelete.username} đã được xóa khỏi hệ thống.`,
        className:
          "bg-green-50 border border-green-300 text-green-700 font-semibold",
        duration: 3000,
      });

      await fetchUsers();
    } catch (error) {
      toast({
        title: "Xóa thất bại",
        description: getApiErrorMessage(error, "Đã xảy ra lỗi khi xóa người dùng."),
        variant: "destructive",
        duration: 3000,
      });

      console.error("Delete error:", error);
    } finally {
      setIsDeleteDialogOpen(false);
      setUserToDelete(null);
    }
  };

  return (
    <div>
      <Card className="automl-data-card mt-2 w-full">
        <CardHeader className="automl-data-toolbar">
          <div>
            <CardTitle className="automl-data-title">
              Quản lý tài khoản người dùng
            </CardTitle>
            <p className="automl-data-subtitle">
              Theo dõi thông tin tài khoản, chỉnh sửa hồ sơ và phân quyền workspace.
            </p>
          </div>
          <div className="automl-data-actions">
            <span className="automl-data-chip">{meta.total_items} người dùng</span>
            <Button
              onClick={() => setIsAddDialogOpen(true)}
              className="automl-action-primary gap-2 px-4"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/15">
                <Plus size={14} />
              </span>
              Thêm mới
            </Button>
          </div>
        </CardHeader>

        <CardContent className="automl-table-wrap pt-5">
          {isLoading ? (
            <AppLoading />
          ) : (
            <>
              <UserTable
                users={users}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
              <PaginationCustom
                currentPage={currentPage}
                totalPages={meta.total_pages || 1}
                onPageChange={setCurrentPage}
              />
            </>
          )}
        </CardContent>
      </Card>
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <UserForm
          editingUser={editingUser}
          onSubmit={onSubmit}
          onClose={handleDialogClose}
        />
      </Dialog>
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
