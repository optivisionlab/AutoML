"use client";

import { useApi } from "@/hooks/useApi";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { CheckCircle2, XCircle, Loader2, Mail, Send, ArrowRight } from "lucide-react";

export default function VerifyEmailPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { post } = useApi();

  const email = params?.get("email");
  const token = params?.get("token");

  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  
  // State cho chức năng gửi lại email
  const [isResending, setIsResending] = useState(false);
  const [resendMessage, setResendMessage] = useState("");

  const isVerifying = useRef(false);

  // Xác minh token
  useEffect(() => {
    if (!token || isVerifying.current) return;

    const verifyToken = async () => {
      isVerifying.current = true;
      setStatus("loading");

      try {
        await post(`/auth/verifications`, { token });
        setStatus("success");

        setTimeout(() => {
          router.push("/login");
        }, 3000);
      } catch (err: any) {
        setStatus("error");
        setErrorMessage(
          err?.response?.data?.detail || 
          err?.response?.data?.message || 
          "Liên kết không hợp lệ hoặc đã hết hạn."
        );
      }
    };

    verifyToken();
  }, [token, post, router]);

  // Gửi lại email
  const handleResendEmail = async () => {
    if (!email) {
      alert("Không tìm thấy thông tin email trên URL. Vui lòng quay lại trang đăng ký.");
      return;
    }

    setIsResending(true);
    setResendMessage("");
    try {
      const response = await post("/auth/token/verifications", { email });
      setResendMessage(response.data?.detail || "Đã gửi lại link xác nhận thành công!");
    } catch (err: any) {
      const errorDetail = err?.response?.data?.detail || "Có lỗi xảy ra khi gửi lại email.";
      alert(errorDetail);
    } finally {
      setIsResending(false);
    }
  };

  // --- RENDERING UI ---

  // Đang loading (gọi API)
  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0f0f0f] px-4 transition-colors duration-300">
        <div className="bg-white dark:bg-[#1a1a1a] border border-transparent dark:border-gray-800 shadow-xl rounded-3xl p-8 max-w-md w-full text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-6" />
          <h1 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">Đang xác minh...</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm animate-pulse">
            Hệ thống đang kiểm tra mã xác nhận của bạn.
          </p>
        </div>
      </div>
    );
  }

  // Đã verify thành công
  if (status === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0f0f0f] px-4 transition-colors duration-300">
        <div className="bg-white dark:bg-[#1a1a1a] border border-transparent dark:border-gray-800 shadow-xl rounded-3xl p-8 max-w-md w-full text-center transform transition-all scale-105">
          <div className="w-20 h-20 bg-green-50 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">
            Xác minh thành công!
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Tài khoản của bạn đã được kích hoạt hoàn toàn.
          </p>
          <div className="flex items-center justify-center gap-2 text-sm font-medium text-blue-600 dark:text-blue-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            Đang chuyển hướng đến trang đăng nhập...
          </div>
        </div>
      </div>
    );
  }

  // Lỗi (Token hết hạn / sai)
  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0f0f0f] px-4 transition-colors duration-300">
        <div className="bg-white dark:bg-[#1a1a1a] border border-transparent dark:border-gray-800 shadow-xl rounded-3xl p-8 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-red-50 dark:bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <XCircle className="w-10 h-10 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">
            Xác minh thất bại
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8 px-2">
            {errorMessage}
          </p>
          <button
            onClick={() => router.push("/register")}
            className="flex items-center justify-center gap-2 w-full bg-gray-900 dark:bg-white text-white dark:text-black py-3.5 rounded-xl font-semibold hover:opacity-90 transition-all"
          >
            Quay lại trang đăng ký <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Chưa verify (Màn hình ban đầu chờ check mail)
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0f0f0f] px-4 transition-colors duration-300">
      <div className="bg-white dark:bg-[#1a1a1a] border border-transparent dark:border-gray-800 shadow-2xl rounded-3xl p-8 max-w-md w-full text-center">
        
        <div className="w-20 h-20 bg-blue-50 dark:bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <Mail className="w-10 h-10 text-blue-600 dark:text-blue-500" />
        </div>

        <h1 className="text-2xl font-bold mb-3 text-gray-900 dark:text-white">
          Kiểm tra hòm thư của bạn
        </h1>
        
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Chúng tôi đã gửi một liên kết xác minh an toàn tới:
        </p>
        
        <div className="mb-8 p-4 bg-gray-50 dark:bg-[#0f0f0f] rounded-2xl border border-gray-100 dark:border-gray-800">
          <p className="font-semibold text-blue-600 dark:text-blue-400 text-lg break-all">
            {email || "Không tìm thấy email"}
          </p>
        </div>

        <div className="space-y-3">
          <a
            href="https://mail.google.com"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 w-full bg-gray-900 dark:bg-white text-white dark:text-black py-3.5 rounded-xl font-semibold hover:opacity-90 transition-all shadow-lg dark:shadow-none"
          >
            Mở Gmail <ArrowRight className="w-4 h-4" />
          </a>

          <button
            onClick={handleResendEmail}
            disabled={isResending || !email}
            className="flex items-center justify-center gap-2 w-full bg-white dark:bg-[#1a1a1a] border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 py-3.5 rounded-xl font-semibold hover:bg-gray-50 dark:hover:bg-gray-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isResending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            {isResending ? "Đang gửi..." : "Gửi lại email xác nhận"}
          </button>
        </div>

        {/* Thông báo gửi lại thành công */}
        {resendMessage && (
          <p className="mt-4 text-sm font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/10 py-2 px-3 rounded-lg">
            {resendMessage}
          </p>
        )}

        <div className="mt-8 pt-6 border-t border-gray-100 dark:border-gray-800">
          <button 
            onClick={() => router.push("/register")} 
            className="text-sm font-medium text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors"
          >
            Sử dụng email khác? <span className="underline">Đăng ký lại</span>
          </button>
        </div>

      </div>
    </div>
  );
}