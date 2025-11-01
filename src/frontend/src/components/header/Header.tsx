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
import { GithubIcon, LogOut, Menu, User2, X } from "lucide-react";
import Image from "next/image";
import ModeToggle from "@/components/mode-toggle";
import { FaGithub } from "react-icons/fa";

export default function Header() {
  const { data: session } = useSession();
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

    fetchAvatar();
    const handleAvatarUpdate = () => fetchAvatar();
    window.addEventListener("avatar-updated", handleAvatarUpdate);
    return () => window.removeEventListener("avatar-updated", handleAvatarUpdate);
  }, [session?.user?.username]);

  return (
    <header className="w-full h-16 border-b px-4 md:px-6 flex items-center justify-between z-50 bg-background">
      <Link href="/" className="flex items-center gap-2 shrink-0" prefetch={false}>
        <Image src="/image.png" priority width={120} height={120} alt="logo" />
      </Link>

      <div className="hidden md:flex items-center gap-10">
        {!session &&
          ["TRANG CHỦ", "GIỚI THIỆU", "VỀ CHÚNG TÔI", "LIÊN HỆ"].map((item, idx) => {
            const hrefs = ["#home", "#introduction", "#about-us", "#contact"];
            return (
              <Link
                href={{
                  pathname: "/",
                  hash: hrefs[idx].replace("#", ""),
                }}
                scroll={true}
                onClick={() => setMobileMenuOpen(false)}
                className="block text-base font-medium text-center py-3 text-foreground hover:text-[#376FF9] transition-colors duration-200"
              >
                {item}
              </Link>
            );
          })}
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="https://github.com/optivisionlab/AutoML"
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-700 dark:text-gray-300 hover:text-black dark:hover:text-white transition-colors"
        >
          <FaGithub className="w-8 h-8" />
        </Link>
        <ModeToggle />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            {session ? (
              <Avatar className="cursor-pointer">
                <AvatarImage src={avatarUrl ?? undefined} alt="avatar" />
                <AvatarFallback className="bg-gray-100">
                  <User2 className="w-6 h-6" />
                </AvatarFallback>
              </Avatar>
            ) : (
              <div className="hidden md:flex items-center space-x-4">
                <Button
                  onClick={() => signIn()}
                  className="bg-[#376FF9] text-white hover:bg-[#2F5ED6] text-base"
                >
                  ĐĂNG NHẬP
                </Button>
                {/* <span >Hoặc</span> */}
                <Button className="bg-[#376FF9] text-white hover:bg-[#2F5ED6]">
                  <Link href={"/register"} className="text-base">ĐĂNG KÝ</Link>
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

        <button className="md:hidden ml-2" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && !session && (
        <div className="absolute top-16 left-0 w-full bg-background px-4 py-3 flex flex-col gap-3 md:hidden z-40 shadow-md border-t">
          {["Trang chủ", "Giới thiệu", "Về chúng tôi", "Liên hệ"].map((item, idx) => {
            const hrefs = ["#home", "#introduction", "#about-us", "#contact"];
            return (
              <Link
                key={idx}
                href={hrefs[idx]}
                className="w-full text-center py-4 border-b border-gray-200 last:border-none text-sm font-medium text-foreground hover:text-[#376FF9] hover:bg-gray-100 transition-colors duration-200"
                onClick={() => setMobileMenuOpen(false)}
              >
                {item}
              </Link>
            );
          })}

          <Button
            onClick={() => signIn()}
            className="w-full bg-[#376FF9] text-white hover:bg-[#2F5ED6]"
          >
            Đăng nhập
          </Button>

          <Link href="/register" className="w-full">
            <Button className="w-full bg-[#376FF9] text-white hover:bg-[#2F5ED6]">
              Đăng ký
            </Button>
          </Link>
        </div>
      )}
    </header>
  );
}