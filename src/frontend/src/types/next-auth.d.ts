// types/next-auth.d.ts
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      username: string;
      email: string;
      role: string;
      avatar: string;
      access_token: string;
      refresh_token: string;
      accessTokenExpires: number;
    };
  }

  interface User {
    id: string;
    username: string;
    email: string;
    role: string;
    avatar: string;
    access_token: string;
    refresh_token: string;
    accessTokenExpires: number;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    username: string;
    email: string;
    role: string;
    avatar: string;
    access_token: string;
    refresh_token: string;
    accessTokenExpires: number;
  }
}
