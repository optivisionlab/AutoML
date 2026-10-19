import { AxiosInstance } from "axios";
import {
  BaseResponse,
  ForgotPasswordPayload,
  LoginPayload,
  RefreshTokenPayload,
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
} from "@automl/domain";

export const createAuthService = (client: AxiosInstance) => ({
  // 1.1 POST /api/v1/auth/signup
  signup: async (payload: SignupPayload): Promise<SignupResponse> => {
    const res = await client.post<SignupResponse>("/api/v1/auth/signup", payload);
    return res.data;
  },

  // 1.2 POST /api/v1/auth/login
  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const res = await client.post<TokenResponse>("/api/v1/auth/login", payload);
    return res.data;
  },

  // 1.3 POST /api/v1/auth/refresh
  refresh: async (payload: RefreshTokenPayload): Promise<TokenResponse> => {
    const res = await client.post<TokenResponse>("/api/v1/auth/refresh", payload);
    return res.data;
  },

  // 1.4 GET /api/v1/auth/me
  getMe: async (): Promise<UserDetailResponse> => {
    const res = await client.get<UserDetailResponse>("/api/v1/auth/me");
    return res.data;
  },

  // 1.5 POST /api/v1/auth/logout
  logout: async (): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>("/api/v1/auth/logout");
    return res.data;
  },

  // 1.7 POST /api/v1/auth/verifications
  verifyEmail: async (payload: VerifyEmailTokenPayload): Promise<VerifyEmailResponse> => {
    const res = await client.post<VerifyEmailResponse>("/api/v1/auth/verifications", payload);
    return res.data;
  },

  // 1.8 POST /api/v1/auth/token/verifications
  resendVerificationToken: async (email: string): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>("/api/v1/auth/token/verifications", { email });
    return res.data;
  },

  // 1.9 POST /api/v1/auth/otp/verifications
  sendOtpVerification: async (payload: SendOtpPayload): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>("/api/v1/auth/otp/verifications", payload);
    return res.data;
  },

  // 1.10 POST /api/v1/auth/forgot-password
  forgotPassword: async (payload: ForgotPasswordPayload): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>("/api/v1/auth/forgot-password", payload);
    return res.data;
  },

  // 1.11 POST /api/v1/auth/verify-otp
  verifyOtp: async (payload: VerifyOtpPayload): Promise<VerifyOtpResponse> => {
    const res = await client.post<VerifyOtpResponse>("/api/v1/auth/verify-otp", payload);
    return res.data;
  },

  // 1.12 POST /api/v1/auth/reset-password
  resetPassword: async (payload: ResetPasswordPayload): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>("/api/v1/auth/reset-password", payload);
    return res.data;
  },

  // Legacy method aliases
  registerUser: async (payload: any): Promise<any> => {
    const res = await client.post("/api/v1/auth/signup", payload);
    return res.data;
  },
  getCurrentUser: async (): Promise<any> => {
    const res = await client.get("/api/v1/auth/me");
    return res.data;
  },
  verifyEmailToken: async (payload: any): Promise<any> => {
    const res = await client.post("/api/v1/auth/verifications", payload);
    return res.data;
  },
  resendVerificationEmail: async (payload: any): Promise<any> => {
    const res = await client.post("/api/v1/auth/token/verifications", payload);
    return res.data;
  },
  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await client.post<TokenResponse>("/api/v1/auth/refresh", { refresh_token: refreshToken });
    return res.data;
  },
});
