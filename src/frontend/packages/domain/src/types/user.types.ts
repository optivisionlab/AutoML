import { BaseResponse, PaginatedResponse, UniversalFile } from "./common.types";

export interface IUser {
  username: string;
  email: string;
  password?: string;
  gender: string;
  date: string;
  number: string;
  role: string;
  avatar?: string | null;
  fullName?: string;
}

export interface User {
  _id: string;
  username: string;
  email: string;
  fullName?: string;
  gender?: string;
  date?: string;
  number?: string;
  role: string;
  avatar?: string | null;
  image?: string;
  is_verified?: boolean;
  created_at?: number;
  password?: string;
}

export interface UpdateUserPayload {
  fullName?: string | null;
  gender?: "male" | "female" | "other" | string | null;
  date?: string | null;
  number?: string | null;
  email?: string;
}

export type CreateUserPayload = UpdateUserPayload & {
  username: string;
  password: string;
  role: string;
  avatar?: string;
};

export interface UpdateAvatarPayload {
  userId?: string;
  username?: string;
  avatar: UniversalFile;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

export interface GetUsersParams {
  page?: number;
  page_size?: number;
}

export type UserDetailResponse = BaseResponse<User>;
export type UsersListResponse = PaginatedResponse<User>;
export type UploadAvatarResponse = BaseResponse<{ avatar: string }>;
