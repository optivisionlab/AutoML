"use client";

import { useApi } from "@/hooks/useApi";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { post } = useApi();

  const email = params.get("email");
  const token = params.get("token");

  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (token) {
      // gọi API verify token
      const verify = async () => {
        try {
          console.log(token);
          await post(`/auth/verifications`, { token });
          setVerified(true);

          // redirect sau 3s
          setTimeout(() => {
            router.push("/login");
          }, 3000);
        } catch (err) {
          console.log(err);
        }
      };

      verify();
    }
  }, [token]);

  // CASE 1: Đã verify thành công
  if (verified) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white shadow-md rounded-2xl p-8 max-w-md w-full text-center">
          <h1 className="text-2xl font-semibold mb-4 text-green-600">
            🎉 Xác minh thành công!
          </h1>

          <p className="text-gray-600 mb-6">
            Tài khoản của bạn đã được kích hoạt.
          </p>

          <p className="text-sm text-gray-500">
            Đang chuyển hướng đến trang đăng nhập...
          </p>
        </div>
      </div>
    );
  }

  // CASE 2: Chưa verify (màn hình ban đầu)
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white shadow-md rounded-2xl p-8 max-w-md w-full text-center">
        <h1 className="text-2xl font-semibold mb-4">
          Hãy xác minh email của bạn
        </h1>

        <p className="text-gray-600 mb-2">
          Chúng tôi đã gửi một liên kết xác minh tới:
        </p>

        <p className="font-medium text-black mb-6">{email}</p>

        <p className="text-gray-500 text-sm mb-6">
          Chỉ cần mở liên kết và bạn sẽ sẵn sàng.
        </p>

        <a
          href="https://mail.google.com"
          target="_blank"
          className="block w-full bg-black text-white py-2 rounded-lg mb-3 hover:opacity-90"
        >
          Mở email
        </a>

        <button
          onClick={() => alert("Call API resend email")}
          className="block w-full border py-2 rounded-lg mb-3 hover:bg-gray-100"
        >
          Gửi lại
        </button>

        <a href="/register" className="text-sm text-gray-500 hover:underline">
          Đăng ký bằng email khác
        </a>
      </div>
    </div>
  );
}
