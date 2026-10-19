"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import RowActionMenu from "@/shared/components/common/RowActionMenu";
import { User } from "@/core/api/userApi";

export default function UserTable({
  users,
  onEdit,
  onDelete,
}: {
  users: User[];
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}) {
  if (users.length === 0) {
    return <div className="automl-state-panel">Không có người dùng nào.</div>;
  }

  return (
    <Table className="automl-data-table">
      <TableHeader>
        <TableRow>
          <TableHead>Tên đăng nhập</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Họ tên</TableHead>
          <TableHead>Mật khẩu</TableHead>
          <TableHead>Giới tính</TableHead>
          <TableHead>Ngày sinh</TableHead>
          <TableHead>SĐT</TableHead>
          <TableHead className="text-center">Tác vụ</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((user) => (
          <TableRow key={user._id} tabIndex={0} className="transition-all outline-none">
            <TableCell className="font-bold text-[var(--automl-data-text)]">
              {user.username}
            </TableCell>
            <TableCell>{user.email}</TableCell>
            <TableCell>{user.fullName}</TableCell>
            <TableCell>{user.password || "Không hiển thị"}</TableCell>
            <TableCell>{user.gender === "male" ? "Nam" : "Nữ"}</TableCell>
            <TableCell>{user.date}</TableCell>
            <TableCell>{user.number}</TableCell>
            <TableCell>
              <div className="flex justify-center">
                <RowActionMenu
                  label={`Mở tác vụ ${user.username}`}
                  items={[
                    { label: "Sửa", onClick: () => onEdit(user) },
                    {
                      label: "Xoá",
                      onClick: () => onDelete(user),
                      destructive: true,
                    },
                  ]}
                />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
