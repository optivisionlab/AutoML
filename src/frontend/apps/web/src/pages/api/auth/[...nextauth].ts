import NextAuth, { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { jwtDecode } from "jwt-decode";

const getBaseApiUrl = (): string => {
  const base = process.env.NEXT_PUBLIC_BASE_API || "http://localhost:9999";
  return base.replace(/\/+$/, "");
};

const getEndpoint = (path: string): string => {
  const base = getBaseApiUrl();
  const cleanPath = path.replace(/^\/+/, "");
  if (base.endsWith("/api/v1") && cleanPath.startsWith("api/v1/")) {
    return `${base}/${cleanPath.replace(/^api\/v1\//, "")}`;
  }
  if (!base.endsWith("/api/v1") && !cleanPath.startsWith("api/v1/")) {
    return `${base}/api/v1/${cleanPath}`;
  }
  return `${base}/${cleanPath}`;
};

async function refreshAccessToken(token: any) {
  try {
    const res = await fetch(getEndpoint("auth/refresh"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        refresh_token: token.refresh_token,
      }),
    });

    const json = await res.json();
    const data = json?.data || json;

    if (!res.ok || !data?.access_token) {
      throw new Error("Refresh token failed");
    }

    const decoded: any = jwtDecode(data.access_token);

    return {
      ...token,
      access_token: data.access_token,
      refresh_token: data.refresh_token || token.refresh_token,
      accessTokenExpires: decoded.exp * 1000, // ms
    };
  } catch {
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
        access_token: { label: "Access Token", type: "text" },
        refresh_token: { label: "Refresh Token", type: "text" },
      },
      async authorize(credentials) {
        // CASE 1: GOOGLE SSO / EMAIL DIRECT TOKEN LOGIN
        if (credentials?.access_token) {
          const access_token = credentials.access_token;
          const refresh_token = credentials.refresh_token || "";

          const decoded: any = jwtDecode(access_token);

          // Gọi API lấy profile user: GET /api/v1/auth/me
          const res = await fetch(getEndpoint("auth/me"), {
            method: "GET",
            headers: {
              Authorization: `Bearer ${access_token}`,
              Accept: "application/json",
            },
          });

          const json = await res.json();
          const userInf = json?.data || json;

          return {
            id: userInf?._id || userInf?.id || decoded.sub || "user",
            username: userInf?.username || decoded.username || "user",
            email: userInf?.email || decoded.email || "",
            role: userInf?.role || decoded.role || "user",
            access_token,
            refresh_token,
            accessTokenExpires: decoded.exp ? decoded.exp * 1000 : Date.now() + 3600 * 1000,
          };
        }

        // CASE 2: LOGIN THƯỜNG BẰNG USERNAME / PASSWORD
        try {
          const { username, password } = credentials as any;

          // POST /api/v1/auth/login
          const res = await fetch(getEndpoint("auth/login"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              username,
              password,
            }),
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => null);
            throw new Error(errData?.detail || "Invalid credentials");
          }

          const json = await res.json();
          const data = json?.data || json;

          if (!data?.access_token) {
            return null;
          }

          const decoded: any = jwtDecode(data.access_token);

          // Lấy thông tin user với access token vừa nhận
          let userInf: any = null;
          try {
            const meRes = await fetch(getEndpoint("auth/me"), {
              method: "GET",
              headers: {
                Accept: "application/json",
                Authorization: `Bearer ${data.access_token}`,
              },
            });

            if (meRes.ok) {
              const meJson = await meRes.json();
              userInf = meJson?.data || meJson;
            }
          } catch (err) {
            console.error("Lỗi khi lấy thông tin user me:", err);
          }

          return {
            id: userInf?._id || userInf?.id || decoded.sub || "user",
            username: userInf?.username || username,
            email: userInf?.email || decoded.email || "",
            role: userInf?.role || decoded.role || "user",
            access_token: data.access_token,
            refresh_token: data.refresh_token || "",
            accessTokenExpires: decoded.exp ? decoded.exp * 1000 : Date.now() + 3600 * 1000,
          };
        } catch (error) {
          console.error("NextAuth authorization error:", error);
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
        token.access_token = user.access_token;
        token.refresh_token = user.refresh_token;
        token.accessTokenExpires = user.accessTokenExpires;
      }

      // Token còn hạn
      if (token.accessTokenExpires && Date.now() < Math.floor(Number(token.accessTokenExpires))) {
        return token;
      }

      // Token hết hạn → refresh token
      return await refreshAccessToken(token);
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.username = token.username as string;
        session.user.email = token.email as string;
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.access_token = token.access_token as string;
        session.user.refresh_token = token.refresh_token as string;
      }
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

  secret: process.env.NEXTAUTH_SECRET || "optivisionlab@hautoml",
};

export default NextAuth(authOptions);
