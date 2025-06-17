import { Home, User, Database, Users, DatabaseZap, History, RocketIcon } from "lucide-react";

export function NavItems(role: string) {
  const commonItems = [
    {
      name: "Trang chủ",
      icon: <Home size={18} />,
      href: "/",
      active: false,
      position: "top",
      role: ["user", "admin"],
    },
  ];

  const userItems = [
    {
      name: "Tài khoản",
      icon: <User size={18} />,
      href: "/profile",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      name: "Bộ dữ liệu có sẵn",
      icon: <Database size={18} />,
      href: "/public-datasets",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      name: "Bộ dữ liệu của tôi",
      icon: <DatabaseZap size={18} />,
      href: "/my-datasets",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      name: "Xem lịch sử huấn luyện",
      icon: <History size={18} />,
      href: "/training-history",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      name: "Triển khai mô hình",
      icon: <RocketIcon size={18} />,
      href: "/implement-project",
      active: false,
      position: "top",
      role: ["user"],
    },
  ];

  const adminItems = [
    {
      name: "Quản lý tài khoản",
      icon: <Users size={18} />,
      href: "/admin/users",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      name: "Bộ dữ liệu có sẵn",
      icon: <Database size={18}/>,
      href: "/admin/datasets/public",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      name: "Bộ dữ liệu của người dùng",
      icon: <DatabaseZap size={18} />,
      href: "/admin/datasets/users",
      active: false,
      position: "top",
      role: ["admin"],
    },
        {
      name: "Xem lịch sử huấn luyện",
      icon: <History size={18} />,
      href: "/training-history",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      name: "Triển khai mô hình",
      icon: <RocketIcon size={18} />,
      href: "/implement-project",
      active: false,
      position: "top",
      role: ["admin"],
    },
  ];

  return [...commonItems, ...userItems, ...adminItems].filter((item) =>
    item.role.includes(role)
  );
}