import NextAuth, { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { jwtDecode } from "jwt-decode";

async function refreshAccessToken(token: any) {
  try {
    console.log("Bắt đầu chưa gọi");
    const res = await fetch(`${process.env.NEXT_PUBLIC_BASE_API}/refresh`, {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },

      body: JSON.stringify({
        refresh_token: token.refresh_token,
      }),
    });

    console.log("Respon: ", res);
    const data = await res.json();

    console.log("Dữ liệu trả:", data);
    const decoded: any = jwtDecode(data.access_token);
    console.log("Token mới là: ", data.access_token);

    return {
      ...token,
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      accessTokenExpires: decoded.exp * 1000, // ms
    };
  } catch (error) {
    return {
      ...token,
      error: "RefreshAccessTokenError",
    };
  }
}

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

          const res = await fetch(`${process.env.NEXT_PUBLIC_BASE_API}/login`, {
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

          const data = await res.json();
          console.log("Data: ", data);

          // Giải mã lấy thông tin
          const decoded: any = jwtDecode(data.access_token);
          console.log("Decoded: ", decoded);

          let userInf: any;
          // Lấy thông tin user có access token
          try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_BASE_API}/me`, {
              method: "GET",
              headers: {
                Accept: "application/json",
                Authorization: `Bearer ${data.access_token}`,
              },
            });

            if (!res.ok) throw new Error("Lỗi khi gọi API");

            const userInf1 = await res.json();
            console.log(userInf1);
            userInf = userInf1;
          } catch (err) {
            console.error("Lỗi khi lấy dữ liệu:", err);
          }

          if (userInf) {
            return {
              id: userInf._id,
              username: userInf.username,
              email: userInf.email,
              role: userInf.role,
              avatar: userInf.avatar,
              access_token: data.access_token,
              refresh_token: data.refresh_token,
              accessTokenExpires: decoded.exp * 1000,
            };
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
      // Login lần đầu
      if (user) {
        token.id = user.id;
        token.username = user.username;
        token.email = user.email;
        token.role = user.role;
        token.avatar = user.avatar;
        token.access_token = user.access_token;
        token.refresh_token = user.refresh_token;
        token.accessTokenExpires = user.accessTokenExpires;
      }

      // Token còn hạn
      console.log("Ngày hiện tại và hạn token");
      console.log(Date.now());
      console.log(token.accessTokenExpires);
      if (Date.now() < Math.floor(token.accessTokenExpires)) {
        console.log("Còn hạn");
        return token;
      }

      // Token hết hạn → refresh
      else {
        console.log("Hêt hạn refresh lại");
        return await refreshAccessToken(token);
      }
    },
    async session({ session, token }) {
      // Gán role từ token vào session.user
      if (token && session.user) {
        session.user.username = token.username as string;
        session.user.email = token.email as string;
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.avatar = token.avatar as string;
        session.user.access_token = token.access_token as string;
        session.user.refresh_token = token.refresh_token as string;
      }
      console.log("Session: ", session);
      return session;
    },
  },

  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 24 * 7,
    updateAge: 60 * 60 * 1,
  },

  pages: {
    signIn: "/login",
  },

  secret: process.env.NEXTAUTH_SECRET,
};

export default NextAuth(authOptions);
