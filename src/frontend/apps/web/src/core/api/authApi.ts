import {
  type ApiMessageResponse,
  type BaseResponse,
  type ForgotPasswordPayload,
  type LoginPayload,
  type RefreshTokenPayload,
  type RegisterUserPayload,
  type ResendVerificationPayload,
  type ResetPasswordPayload,
  type SendOtpPayload,
  type SignupPayload,
  type SignupResponse,
  type TokenResponse,
  type UserDetailResponse,
  type VerifyEmailResponse,
  type VerifyEmailTokenPayload,
  type VerifyOtpPayload,
  type VerifyOtpResponse,
} from "@automl/domain";
import { baseApi } from "./baseApi";

export type {
  ApiMessageResponse,
  BaseResponse,
  ForgotPasswordPayload,
  LoginPayload,
  RefreshTokenPayload,
  RegisterUserPayload,
  ResendVerificationPayload,
  ResetPasswordPayload,
  SendOtpPayload,
  SignupPayload,
  SignupResponse,
  TokenResponse,
  UserDetailResponse,
  VerifyEmailResponse,
  VerifyEmailTokenPayload,
  VerifyOtpPayload,
  VerifyOtpResponse,
};

export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 1.1 POST /api/v1/auth/signup
    registerUser: builder.mutation<SignupResponse, SignupPayload | RegisterUserPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/signup",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth", "User"],
    }),

    // 1.2 POST /api/v1/auth/login
    login: builder.mutation<TokenResponse, LoginPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/login",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),

    // 1.3 POST /api/v1/auth/refresh
    refreshToken: builder.mutation<TokenResponse, RefreshTokenPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/refresh",
        method: "POST",
        data: payload,
      }),
    }),

    // 1.4 GET /api/v1/auth/me
    getCurrentUser: builder.query<UserDetailResponse, void>({
      query: () => ({
        url: "/api/v1/auth/me",
      }),
      providesTags: ["Auth"],
    }),

    // 1.5 POST /api/v1/auth/logout
    logout: builder.mutation<BaseResponse<null>, void>({
      query: () => ({
        url: "/api/v1/auth/logout",
        method: "POST",
      }),
      invalidatesTags: ["Auth"],
    }),

    // 1.7 POST /api/v1/auth/verifications
    verifyEmailToken: builder.mutation<
      VerifyEmailResponse,
      VerifyEmailTokenPayload
    >({
      query: (payload) => ({
        url: "/api/v1/auth/verifications",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),

    // 1.8 POST /api/v1/auth/token/verifications
    resendVerificationEmail: builder.mutation<
      BaseResponse<null>,
      ResendVerificationPayload
    >({
      query: (payload) => ({
        url: "/api/v1/auth/token/verifications",
        method: "POST",
        data: payload,
      }),
    }),

    // 1.9 POST /api/v1/auth/otp/verifications
    sendOtpVerification: builder.mutation<
      BaseResponse<null>,
      SendOtpPayload
    >({
      query: (payload) => ({
        url: "/api/v1/auth/otp/verifications",
        method: "POST",
        data: payload,
      }),
    }),

    // 1.10 POST /api/v1/auth/forgot-password
    forgotPassword: builder.mutation<BaseResponse<null>, ForgotPasswordPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/forgot-password",
        method: "POST",
        data: payload,
      }),
    }),

    // 1.11 POST /api/v1/auth/verify-otp
    verifyOtp: builder.mutation<VerifyOtpResponse, VerifyOtpPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/verify-otp",
        method: "POST",
        data: payload,
      }),
    }),

    // 1.12 POST /api/v1/auth/reset-password
    resetPassword: builder.mutation<BaseResponse<null>, ResetPasswordPayload>({
      query: (payload) => ({
        url: "/api/v1/auth/reset-password",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),
  }),
});

export const {
  useForgotPasswordMutation,
  useGetCurrentUserQuery,
  useLazyGetCurrentUserQuery,
  useLoginMutation,
  useLogoutMutation,
  useRefreshTokenMutation,
  useRegisterUserMutation,
  useResendVerificationEmailMutation,
  useResetPasswordMutation,
  useSendOtpVerificationMutation,
  useVerifyEmailTokenMutation,
  useVerifyOtpMutation,
} = authApi;
