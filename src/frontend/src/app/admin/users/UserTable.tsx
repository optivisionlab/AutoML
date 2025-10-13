"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2 } from "lucide-react";
import { User } from "@/hooks/useUsers";

export default function UserTable({
  users,
  onEdit,
  onDelete,
}: {
  users: User[];
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Tên đăng nhập</TableHead>
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
                  onClick={() => onEdit(user)}
                >
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => onDelete(user)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
