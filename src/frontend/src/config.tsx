import { usePathname } from "next/navigation"

import { Home, User, Database } from "lucide-react";

export const NavItems = () => {
  const pathname = usePathname();

  // function isNavItemActive(pathname: string, nav: string){
  //   return pathname.includes(nav);
  // }

  return [
    {
      name: 'Trang chủ',
      href: '/',
      icon: <Home size={20} />,
      active: pathname === '/',
      position: 'top',
    },
    {
      name: 'Tài khoản',
      href: '/profile',
      icon: <User size={20} />,
      active: pathname === '/profile',
      position: 'top',
    },
    {
      name: 'Bộ dữ liệu',
      href: '/dataset',
      icon: <Database size={20} />,
      active: pathname === '/dataset',
      position: 'top',
    }
  ]
}