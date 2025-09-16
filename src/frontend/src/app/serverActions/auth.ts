"use server";

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
      return { ok: false, error: "Gửi yêu cầu thất bại" };
    }

    const data = await res.json();
    return { ok: true, data };
  } catch (error: any) {
    return { ok: false, error: error.message || "Có lỗi xảy ra" };
  }
}
