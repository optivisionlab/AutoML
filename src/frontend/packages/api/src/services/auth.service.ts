import { AxiosInstance } from "axios";
import {
  ApiMessageResponse,
  ForgotPasswordPayload,
  LoginPayload,
  RegisterUserPayload,
  ResendVerificationPayload,
  ResetPasswordPayload,
  SendOtpPayload,
  TokenResponse,
  VerifyEmailTokenPayload,
  VerifyOtpPayload,
} from "@automl/domain";

export const createAuthService = (client: AxiosInstance) => ({
  registerUser: async (payload: RegisterUserPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/signup", payload);
    return res.data;
  },

  getCurrentUser: async (): Promise<ApiMessageResponse> => {
    const res = await client.get<ApiMessageResponse>("/me");
    return res.data;
  },

  forgotPassword: async (payload: ForgotPasswordPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/forgot-password", payload);
    return res.data;
  },

  resetPassword: async (payload: ResetPasswordPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/reset-password", payload);
    return res.data;
  },

  verifyEmailToken: async (payload: VerifyEmailTokenPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/auth/verifications", payload);
    return res.data;
  },

  resendVerificationEmail: async (
    payload: ResendVerificationPayload
  ): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/auth/token/verifications", payload);
    return res.data;
  },

  verifyOtp: async (payload: VerifyOtpPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/auth/verify-otp", payload);
    return res.data;
  },

  sendOtpVerification: async (payload: SendOtpPayload): Promise<ApiMessageResponse> => {
    const res = await client.post<ApiMessageResponse>("/auth/otp/verifications", payload);
    return res.data;
  },

  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const res = await client.post<TokenResponse>("/login", payload);
    return res.data;
  },

  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await client.post<TokenResponse>("/refresh", { refresh_token: refreshToken });
    return res.data;
  },
});
