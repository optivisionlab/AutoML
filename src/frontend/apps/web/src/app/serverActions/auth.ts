"use server";

import { getSession } from "next-auth/react";
import { getPublicEnv } from "@/core/config/publicEnv";

// Server action chạy phía server - xem ghi chú INTERNAL_API_URL trong
// pages/api/auth/[...nextauth].ts.
const getApiUrl = () =>
  process.env.INTERNAL_API_URL || getPublicEnv("NEXT_PUBLIC_BASE_API");
// Quên mật khẩu -> gọi yêu cầu gửi
export async function forgotPassword(email: string) {
  const session = await getSession();

  try {
    const res = await fetch(
      `${getApiUrl()}/forgot-password?email=${email}`,
      {
        method: "POST",
        headers: {
          accept: "application/json",
          Authorization: `Bearer ${session?.user?.access_token}`,
        },
      },
    );

    if (!res.ok) {
      return { ok: false, error: "Email chưa được đăng kí hoặc không tồn tại" };
    }

    const data = await res.json();
    return { ok: true, data };
  } catch (error: any) {
    return { ok: false, error: error.message || "Có lỗi xảy ra" };
  }
}

// Thay đổi mk
export async function changePassword(
  email: string,
  password: string,
  new1_password: string,
  new2_password: string,
) {
  // const session = await getSession();

  const res = await fetch(
    `${getApiUrl()}/reset-password`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
        // Authorization: `Bearer ${session?.user?.access_token}`,
      },
      body: JSON.stringify({
        email,
        password,
        new_password: new1_password,
        confirm_password: new2_password,
      }),
    },
  );
  const data = await res.json();

  if (!res.ok) {
    return { ok: false, error: data.detail || "Có lỗi xảy ra" };
  }

  return { ok: true, noError: data.detail };
}
