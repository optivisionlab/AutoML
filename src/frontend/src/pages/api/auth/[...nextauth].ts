import NextAuth, { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: {
          label: "Username",
          type: "text",
          placeholder: "Nguyen Van A",
        },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        try {
          const { username, password } = credentials as any;

          const res = await fetch(`http://10.100.200.119:9999/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              username,
              password,
            }),
          });

          if (!res.ok) {
            throw new Error("Invalid credentials");
          }

          const user = await res.json();

          if (user) {
            return {
              id: user.id,
              username: user.username,
              email: user.email,
              role: user.role,
              avatar: user.avatar,
            }
          } else {
            return null;
          }
        } catch (error) {
          console.error("Authorization error:", error);
          return null;
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user }) {
      // Gán role vào token khi đăng nhập lần đầu
      if (user) {
        token.username = user.username;
        token.email = user.email;
        token.id = user.id;
        token.role = user.role;
        token.avatar = user.avatar;
      }
      return token;
    },
    async session({ session, token }) {
      // Gán role từ token vào session.user
      if (token && session.user) {
        session.user.username = token.username as string;
        session.user.email = token.email as string;
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.avatar = token.avatar as string;
      }
      return session;
    },
  },
  
  session: {
    strategy: "jwt",
  },

  pages: {
    signIn: "/login",
  },

  secret: process.env.NEXTAUTH_SECRET,
};

export default NextAuth(authOptions);
