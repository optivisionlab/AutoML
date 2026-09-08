import {
  Database,
  DatabaseZap,
  History,
  LayoutDashboard,
  MapPinHouse,
  RocketIcon,
  Users,
} from "lucide-react";

export function NavItems(role: string) {
  const commonItems = [
    {
      labelKey: "dashboard",
      icon: <LayoutDashboard size={18} />,
      href: "/dashboard",
      active: false,
      position: "top",
      role: ["user", "admin"],
    },
  ];

  const userItems = [
    {
      labelKey: "publicDatasets",
      icon: <Database size={18} />,
      href: "/public-datasets",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      labelKey: "myDatasets",
      icon: <DatabaseZap size={18} />,
      href: "/my-datasets",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      labelKey: "trainingHistory",
      icon: <History size={18} />,
      href: "/training-history",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      labelKey: "deployModel",
      icon: <RocketIcon size={18} />,
      href: "/implement-project",
      active: false,
      position: "top",
      role: ["user"],
    },
    {
      labelKey: "modelStore",
      icon: <MapPinHouse size={18} />,
      href: "/market-place",
      active: false,
      position: "top",
      role: ["user"],
    },
  ];

  const adminItems = [
    {
      labelKey: "accountManagement",
      icon: <Users size={18} />,
      href: "/admin/users",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      labelKey: "publicDatasets",
      icon: <Database size={18} />,
      href: "/admin/datasets/public",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      labelKey: "userDatasets",
      icon: <DatabaseZap size={18} />,
      href: "/admin/datasets/users",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      labelKey: "trainingHistory",
      icon: <History size={18} />,
      href: "/training-history",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      labelKey: "deployModel",
      icon: <RocketIcon size={18} />,
      href: "/implement-project",
      active: false,
      position: "top",
      role: ["admin"],
    },
    {
      labelKey: "modelStore",
      icon: <MapPinHouse size={18} />,
      href: "/market-place",
      active: false,
      position: "top",
      role: ["admin"],
    },
  ];

  return [...commonItems, ...userItems, ...adminItems].filter((item) =>
    item.role.includes(role),
  );
}
