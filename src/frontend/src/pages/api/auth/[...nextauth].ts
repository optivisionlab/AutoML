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

          const res = await fetch(`http://localhost:9999/login`, {
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
            // user.name = user.username;
            // return user;
            return {
              id: user.id,
              username: user.username,
              email: user.email,
              role: user.role,
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
        token.name = user.name || user.email.split('@')[0];
        token.role = user.role;
      }
      return token;
    },
    async session({ session, token }) {
      // Gán role từ token vào session.user
      if (token && session.user) {
        // session.user.name = token.name;
        session.user.role = token.role as string;
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
