"use server";

import { error } from "console";

// Quên mật khẩu -> gọi yêu cầu gửi
export async function forgotPassword(email: string) {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BASE_API}/forgot_password/${email}`,
      {
        method: "POST",
        headers: {
          accept: "application/json",
        },
      }
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
  username: string,
  password: string,
  new1_password: string,
  new2_password: string
) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BASE_API}/change_password?username=${username}`,
    {
      method: "POST",
      headers: {
        accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
        new1_password,
        new2_password,
      }),
    }
  );
  const data = await res.json();

  if (!res.ok) {
    return { ok: false, error: data.detail || "Có lỗi xảy ra" };
  }

  return { ok: true, noError: data.detail };
}
