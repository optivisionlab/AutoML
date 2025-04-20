import { Home, User, Database, Users, Folder } from "lucide-react";

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
      name: "Bộ dữ liệu",
      icon: <Database size={18} />,
      href: "/datasets",
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
      name: "Quản lý bộ dữ liệu",
      icon: <Folder size={18} />,
      href: "/admin/datasets",
      active: false,
      position: "top",
      role: ["admin"],
    },
  ];

  return [...commonItems, ...userItems, ...adminItems].filter((item) =>
    item.role.includes(role)
  );
}