"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RefreshCwIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from "@/components/ui/input-otp";

export default function VerifyOTPForm() {
  const params = useSearchParams();
  const router = useRouter();

  const email = params?.get("email") || "";
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);

  const [timeLeft, setTimeLeft] = useState(60);

  // Gọi API verify
  const handleVerify = async () => {
    if (timeLeft <= 0) {
      alert("Mã OTP đã hết hạn, vui lòng gửi lại");
      return;
    }

    if (otp.length !== 6) {
      alert("Vui lòng nhập đầy đủ mã OTP");
      return;
    }

    try {
      setLoading(true);

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/auth/verify-otp`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, otp }),
        },
      );

      if (!res.ok) {
        throw new Error("Xác thực thất bại");
      }

      const data: any = await res.json(); // FIX thiếu await
      console.log(data);

      const epOld = {
        oldPassword: data.password,
        email: email,
      };

      localStorage.setItem("verify-info", JSON.stringify(epOld));

      router.push("/change-pw");
    } catch (error) {
      alert("Mã OTP không đúng hoặc đã hết hạn");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_BASE_API}/auth/otp/verifications`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email }),
        },
      );

      setTimeLeft(60); // reset timer
      setOtp(""); // clear otp (optional)
      alert("Đã gửi lại mã OTP");
    } catch (err) {
      alert("Không thể gửi lại OTP");
    }
  };

  useEffect(() => {
    if (timeLeft <= 0) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft]);

  return (
    <Card className="mx-auto max-w-md mt-20">
      <CardHeader>
        <CardTitle className="text-center mb-2">Xác thực tài khoản</CardTitle>
        <CardDescription>
          Nhập mã OTP đã được gửi tới email:
          <span className="block font-semibold mt-1">{email}</span>
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Field>
          <div className="flex items-center justify-between">
            <FieldLabel>Mã xác thực</FieldLabel>
            <Button variant="outline" size="xs" onClick={handleResend}>
              <RefreshCwIcon className="mr-1 h-4 w-4" />
              Gửi lại
            </Button>
          </div>

          <InputOTP
            maxLength={6}
            value={otp}
            onChange={(value) => setOtp(value)}
          >
            <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl">
              <InputOTPSlot index={0} />
              <InputOTPSlot index={1} />
              <InputOTPSlot index={2} />
            </InputOTPGroup>

            <InputOTPSeparator className="mx-2" />

            <InputOTPGroup className="*:data-[slot=input-otp-slot]:h-12 *:data-[slot=input-otp-slot]:w-11 *:data-[slot=input-otp-slot]:text-xl">
              <InputOTPSlot index={3} />
              <InputOTPSlot index={4} />
              <InputOTPSlot index={5} />
            </InputOTPGroup>
          </InputOTP>

          <FieldDescription>
            Không nhận được mã? Kiểm tra spam hoặc bấm "Gửi lại".
          </FieldDescription>

          <FieldDescription>
            {timeLeft > 0 ? (
              <span className="text-blue-500">
                Mã OTP sẽ hết hạn sau: {timeLeft}s
              </span>
            ) : (
              <span className="text-red-500">Mã OTP đã hết hạn</span>
            )}
          </FieldDescription>
        </Field>
      </CardContent>

      <CardFooter>
        <Field>
          <Button
            type="button"
            className="w-full bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
            onClick={handleVerify}
            disabled={loading}
          >
            {loading ? "Đang xác thực..." : "Xác nhận"}
          </Button>

          <div className="text-sm text-muted-foreground text-center mt-2">
            Nhập sai email?{" "}
            <a
              href="/register"
              className="underline underline-offset-4 hover:text-primary"
            >
              Đăng ký lại
            </a>
          </div>
        </Field>
      </CardFooter>
    </Card>
  );
}
