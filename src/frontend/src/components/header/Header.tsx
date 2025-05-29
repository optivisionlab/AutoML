"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { signIn, signOut, useSession } from "next-auth/react";
import { LogOut, User2 } from "lucide-react";
import Image from "next/image";

export default function Header() {
  const { data: session } = useSession();
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);

  useEffect(() => {
    const fetchAvatar = async () => {
      if (session?.user?.username) {
        try {
          const res = await fetch(
            `${process.env.NEXT_PUBLIC_BASE_API}/get_avatar/${session.user.username}`
          );
          if (!res.ok) throw new Error("Avatar fetch failed");

          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          setAvatarUrl(url);
        } catch (error) {
          console.log("Avatar fetch error:", error);
        }
      }
    };

    fetchAvatar(); // Lấy avatar lần đầu khi component mount

    const handleAvatarUpdate = () => {
      fetchAvatar(); // Refetch lại avatar nếu có event cập nhật
    };

    window.addEventListener("avatar-updated", handleAvatarUpdate);

    // Cleanup khi unmount
    return () => {
      window.removeEventListener("avatar-updated", handleAvatarUpdate);
    };
  }, [session?.user?.username]);

  return (
    <header className="flex items-center h-16 px-4 border-b shrink-0 md:px-6 justify-between">
      <Link
        href="/"
        className="flex items-center gap-2 text-lg font-semibold md:text-base"
        prefetch={false}
      >
        <Image src="/image.png" priority width={150} height={150} alt="logo" />
      </Link>

      {!session && (
        <div className="md:flex items-center gap-10">
          <Link
            href="/"
            className="text-sm font-medium text-black hover:text-[#3D6DF6]"
          >
            Trang chủ
          </Link>
          <Link
            href="/"
            className="text-sm font-medium text-black hover:text-[#3D6DF6]"
          >
            Giới thiệu
          </Link>
          <Link
            href="/"
            className="text-sm font-medium text-black hover:text-[#3D6DF6]"
          >
            Về chúng tôi
          </Link>
          <Link
            href="/"
            className="text-sm font-medium text-black hover:text-[#3D6DF6]"
          >
            Liên hệ
          </Link>
        </div>
      )}

      <div className="ml-4 flex items-center gap-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            {session ? (
              <Avatar className="cursor-pointer">
                <AvatarImage src={avatarUrl ?? undefined} alt="avatar" />
                <AvatarFallback className=" bg-gray-100">
                  <User2 className="w-6 h-6" />
                </AvatarFallback>
              </Avatar>
            ) : (
              <div className="flex items-center justify-center space-x-4">
                <Button
                  onClick={() => signIn()}
                  className="bg-[#376FF9] text-white hover:bg-[#2F5ED6]"
                >
                  Đăng nhập
                </Button>
                <span className="text-black"> Hoặc</span>
                <Button className="bg-[#376FF9] text-white hover:bg-[#2F5ED6]">
                  <Link href={"/register"}>Đăng ký</Link>
                </Button>
              </div>
            )}
          </DropdownMenuTrigger>
          {session && (
            <DropdownMenuContent>
              <DropdownMenuLabel>{session.user?.username}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => signOut()}>
                Đăng xuất <LogOut size={16} className="ml-2 text-red-600" />
              </DropdownMenuItem>
            </DropdownMenuContent>
          )}
        </DropdownMenu>
      </div>
    </header>
  );
}
