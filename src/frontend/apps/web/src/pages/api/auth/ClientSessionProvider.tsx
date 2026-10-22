"use client";

import { SessionProvider } from "next-auth/react";
import { ReactNode } from "react";

export default function ClientSessionProvider({ children }: { children: ReactNode }) {
  // Watcher nhận token mới từ phiên web, kể cả khi người dùng chỉ chờ job xong.
  return <SessionProvider refetchInterval={60}>{children}</SessionProvider>;
}
