"use client";

import { signIn } from "next-auth/react";
import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";

export default function GoogleCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const access_token = searchParams.get("access_token");
  const refresh_token = searchParams.get("refresh_token");

  useEffect(() => {
    if (access_token && refresh_token) {
      signIn("credentials", {
        access_token,
        refresh_token,
        redirect: false, // nên để false để tự control
      }).then((res) => {
        if (res?.ok) {
          router.replace("/"); // redirect sau khi login thành công
        } else {
          router.replace("/login"); // fail thì quay lại login
        }
      });
    }
  }, [access_token, refresh_token]);

  return <p>Đang đăng nhập bằng Google...</p>;
}
