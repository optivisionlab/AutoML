import { ApiMessageResponse, BaseResponse } from "./common.types";
import { IUser, User } from "./user.types";

export interface SignupPayload {
  username: string;
  email: string;
  password: string;
  fullName: string;
  gender: "male" | "female" | "other" | string;
  date: string;
  number: string;
}

export type SignupResponseData = User;
export type SignupResponse = BaseResponse<SignupResponseData>;

export interface LoginPayload {
  username: string;
  password?: string;
}

export interface TokenResponseData {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export type TokenResponse = BaseResponse<TokenResponseData>;

export interface RefreshTokenPayload {
  refresh_token: string;
}

export type CurrentUserResponseData = User;
export type CurrentUserResponse = BaseResponse<CurrentUserResponseData>;

export interface VerifyEmailTokenPayload {
  token: string;
}

export type VerifyEmailResponse = BaseResponse<TokenResponseData>;

export interface ResendVerificationPayload {
  email: string;
}

export interface SendOtpPayload {
  email: string;
}

export interface ForgotPasswordPayload {
  email: string;
}

export interface VerifyOtpPayload {
  email: string;
  otp: string;
}

export interface VerifyOtpResponseData {
  reset_token: string;
}

export type VerifyOtpResponse = BaseResponse<VerifyOtpResponseData>;

export interface ResetPasswordPayload {
  token: string;
  new_password: string;
  confirm_password: string;
}

export type RegisterUserPayload = SignupPayload | IUser;

export type { ApiMessageResponse };
