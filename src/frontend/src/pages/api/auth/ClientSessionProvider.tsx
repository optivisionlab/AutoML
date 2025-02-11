"use client";

import { SessionProvider } from "next-auth/react";
import { ReactNode } from "react";

interface Props {
  children: ReactNode;
  session: any;
}

export default function ClientSessionProvider({ children, session }: Props) {
  return <SessionProvider session={session}>{children}</SessionProvider>;
}