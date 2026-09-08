import { ApiMessageResponse } from "./common.types";
import { IUser } from "./user.types";

export type RegisterUserPayload = IUser;

export type LoginPayload = {
  username: string;
  password?: string;
  access_token?: string;
  refresh_token?: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export type ForgotPasswordPayload = {
  email: string;
};

export type ResetPasswordPayload = {
  token?: string;
  password?: string;
  [key: string]: unknown;
};

export type VerifyEmailTokenPayload = {
  token: string;
};

export type ResendVerificationPayload = {
  email: string;
};

export type VerifyOtpPayload = {
  email: string;
  otp: string;
};

export type SendOtpPayload = {
  email: string;
};

export type { ApiMessageResponse };
