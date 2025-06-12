import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware(req) {
    const { pathname } = req.nextUrl;
    const role = req.nextauth.token?.role;

    // Nếu đã đăng nhập mà truy cập /login hoặc /register thì redirect về trang chính
    if (
      req.nextauth.token && 
      (pathname === "/login" || pathname === "/register")
    ) {
      return NextResponse.redirect(new URL("/", req.url)); // Hoặc /profile nếu bạn có
    }

    // Nếu route là admin nhưng role không phải admin => redirect
    if (
      pathname.startsWith("/admin/users") ||
      pathname.startsWith("/admin/datasets")
    ) {
      if (role !== "admin") {
        return NextResponse.redirect(new URL("/", req.url)); // hoặc về /unauthorized
      }
    }

    // Các route khác không cần chặn ở đây
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token }) => !!token, // chỉ cần có token là cho qua bước đầu
    },
  }
);

export const config = {
  matcher: [
    "/login",
    "/register",
    "/register/:path*",
    "/login/:path*",
    "/profile/:path*",
    "/datasets/:path*",
    "/public-datasets/:path*",
    "/my-datasets/:path*",
    "/implement-project/:path*",
    "/training-history/:path*",
    "/available-datasets/:path*",
    "/admin/users/:path*",
    "/admin/datasets/:path*",
  ],
};