import {
  type ApiMessageResponse,
  type RegisterUserPayload,
  type ForgotPasswordPayload,
  type VerifyEmailTokenPayload,
  type ResendVerificationPayload,
  type VerifyOtpPayload,
  type SendOtpPayload,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  ApiMessageResponse,
  RegisterUserPayload,
  ForgotPasswordPayload,
  VerifyEmailTokenPayload,
  ResendVerificationPayload,
  VerifyOtpPayload,
  SendOtpPayload,
};

// Các api auth
export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // API đăng ký tài khoản.
    registerUser: builder.mutation<ApiMessageResponse, RegisterUserPayload>({
      query: (payload) => ({
        url: "/signup",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth", "User"],
    }),

    // API lấy thông tin người dùng đang đăng nhập.
    getCurrentUser: builder.query<ApiMessageResponse, void>({
      query: () => ({
        url: "/me",
      }),
      providesTags: ["Auth"],
    }),

    // API yêu cầu gửi email đặt lại mật khẩu.
    forgotPassword: builder.mutation<ApiMessageResponse, ForgotPasswordPayload>({
      query: (payload) => ({
        url: "/forgot-password",
        method: "POST",
        data: payload,
      }),
    }),

    // API đặt lại mật khẩu.
    resetPassword: builder.mutation<ApiMessageResponse, unknown>({
      query: (payload) => ({
        url: "/reset-password",
        method: "POST",
        data: payload,
      }),
    }),

    // API xác thực mã OTP.
    verifyEmailToken: builder.mutation<
      ApiMessageResponse,
      VerifyEmailTokenPayload
    >({
      query: (payload) => ({
        url: "/auth/verifications",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),

    resendVerificationEmail: builder.mutation<
      ApiMessageResponse,
      ResendVerificationPayload
    >({
      query: (payload) => ({
        url: "/auth/token/verifications",
        method: "POST",
        data: payload,
      }),
    }),

    verifyOtp: builder.mutation<ApiMessageResponse, VerifyOtpPayload>({
      query: (payload) => ({
        url: "/auth/verify-otp",
        method: "POST",
        data: payload,
      }),
    }),

    sendOtpVerification: builder.mutation<
      ApiMessageResponse,
      SendOtpPayload
    >({
      query: (payload) => ({
        url: "/auth/otp/verifications",
        method: "POST",
        data: payload,
      }),
    }),
  }),
});

export const {
  useForgotPasswordMutation,
  useGetCurrentUserQuery,
  useRegisterUserMutation,
  useResendVerificationEmailMutation,
  useResetPasswordMutation,
  useSendOtpVerificationMutation,
  useVerifyEmailTokenMutation,
  useVerifyOtpMutation,
} = authApi;
