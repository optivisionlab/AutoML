"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RefreshCwIcon } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/shared/components/ui/field";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "@/shared/components/ui/input-otp";
import {
  useForgotPasswordMutation,
  useVerifyOtpMutation,
} from "@/core/api/authApi";
import { getApiErrorMessage } from "@/core/api/baseApi";
import { useToast } from "@/shared/hooks/use-toast";

export default function VerifyOTPForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { toast } = useToast();

  const email = params?.get("email") || "";
  const [otp, setOtp] = useState("");
  const [verifyOtp, { isLoading: isVerifying }] = useVerifyOtpMutation();
  const [forgotPassword, { isLoading: isResending }] =
    useForgotPasswordMutation();

  const [timeLeft, setTimeLeft] = useState(300); // OTP hạn 5 phút (300 giây)

  // Gọi API xác thực OTP
  const handleVerify = async () => {
    if (timeLeft <= 0) {
      toast({
        title: "Mã OTP đã hết hạn",
        description: "Vui lòng bấm 'Gửi lại' để nhận mã OTP mới.",
        variant: "destructive",
      });
      return;
    }

    if (otp.length !== 6) {
      toast({
        title: "Mã OTP không đủ",
        description: "Vui lòng nhập đầy đủ mã OTP gồm 6 chữ số.",
        variant: "destructive",
      });
      return;
    }

    try {
      const res = await verifyOtp({ email, otp }).unwrap();
      const resetToken = res?.data?.reset_token;

      if (resetToken) {
        sessionStorage.setItem("reset_token", resetToken);
        toast({
          title: "Xác thực OTP thành công!",
          description: "Vui lòng nhập mật khẩu mới.",
          className: "bg-green-100 text-green-800 border border-green-300",
        });

        router.push(
          `/change-pw?token=${encodeURIComponent(resetToken)}&email=${encodeURIComponent(email)}`,
        );
      } else {
        throw new Error("Không nhận được mã xác nhận đặt lại mật khẩu.");
      }
    } catch (error) {
      toast({
        title: "Xác thực thất bại",
        description: getApiErrorMessage(
          error,
          "Mã OTP không chính xác hoặc đã hết hạn.",
        ),
        variant: "destructive",
      });
    }
  };

  const handleResend = async () => {
    if (!email) {
      toast({
        title: "Thiếu email",
        description: "Vui lòng quay lại trang quên mật khẩu để nhập email.",
        variant: "destructive",
      });
      return;
    }

    try {
      await forgotPassword({ email }).unwrap();
      setTimeLeft(300); // reset 5 phút
      setOtp("");
      toast({
        title: "Đã gửi lại OTP!",
        description: "Mã OTP mới đã được gửi tới email của bạn.",
        className: "bg-green-100 text-green-800 border border-green-300",
      });
    } catch (err) {
      toast({
        title: "Lỗi gửi lại",
        description: getApiErrorMessage(err, "Không thể gửi lại mã OTP."),
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    if (timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <Card className="mx-auto max-w-md mt-16 rounded-3xl border border-slate-200 bg-white dark:border-white/10 dark:bg-automl-navy shadow-sm">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl font-black text-slate-900 dark:text-white mb-1">
          Nhập mã xác thực OTP
        </CardTitle>
        <CardDescription className="text-slate-500 dark:text-slate-400">
          Nhập mã OTP 6 số đã được gửi tới email:
          <span className="block font-bold text-blue-600 dark:text-blue-400 mt-1">
            {email || "Chưa có email"}
          </span>
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Field className="space-y-3">
          <div className="flex items-center justify-between">
            <FieldLabel className="font-bold text-slate-700 dark:text-slate-300">
              Mã xác thực 6 số
            </FieldLabel>
            <Button
              variant="outline"
              size="sm"
              onClick={handleResend}
              disabled={isResending}
              className="rounded-xl font-semibold"
            >
              <RefreshCwIcon className={`mr-1 h-3.5 w-3.5 ${isResending ? "animate-spin" : ""}`} />
              Gửi lại
            </Button>
          </div>

          <div className="flex justify-center py-2">
            <InputOTP
              maxLength={6}
              value={otp}
              onChange={(value) => setOtp(value)}
            >
              <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl *:data-[slot=input-otp-slot]:font-bold">
                <InputOTPSlot index={0} />
                <InputOTPSlot index={1} />
                <InputOTPSlot index={2} />
              </InputOTPGroup>

              <InputOTPSeparator className="mx-2" />

              <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl *:data-[slot=input-otp-slot]:font-bold">
                <InputOTPSlot index={3} />
                <InputOTPSlot index={4} />
                <InputOTPSlot index={5} />
              </InputOTPGroup>
            </InputOTP>
          </div>

          <FieldDescription className="text-center text-xs text-slate-500 dark:text-slate-400">
            {timeLeft > 0 ? (
              <span className="text-blue-600 dark:text-blue-400 font-semibold">
                Mã OTP sẽ hết hạn sau: {formatTimer(timeLeft)}
              </span>
            ) : (
              <span className="text-rose-500 font-bold">Mã OTP đã hết hạn</span>
            )}
          </FieldDescription>
        </Field>
      </CardContent>

      <CardFooter>
        <Field className="w-full space-y-3">
          <Button
            type="button"
            className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7] h-11 rounded-xl font-bold"
            onClick={handleVerify}
            disabled={isVerifying || otp.length !== 6}
          >
            {isVerifying ? "Đang xác minh..." : "Xác nhận OTP"}
          </Button>

          <div className="text-sm text-center">
            <a
              href="/forgot-pw"
              className="text-slate-500 hover:text-blue-600 text-xs font-semibold"
            >
              Nhập sai email? Yêu cầu lại
            </a>
          </div>
        </Field>
      </CardFooter>
    </Card>
  );
}
