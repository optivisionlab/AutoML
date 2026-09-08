import { UniversalFile } from "./common.types";

export interface IUser {
  username: string;
  email: string;
  password: string;
  gender: string;
  date: string;
  number: string;
  role: string;
  avatar: string;
}

export type User = {
  _id: string;
  username: string;
  email: string;
  password?: string;
  gender: string;
  date: string;
  number: string;
  role: string;
  fullName: string;
  avatar?: string;
  image?: string;
};

export type UpdateUserPayload = {
  email: string;
  gender: string;
  date: string;
  fullName: string;
  number: string;
};

export type CreateUserPayload = UpdateUserPayload & {
  username: string;
  password: string;
  role: string;
  avatar?: string;
};

export type UpdateAvatarPayload = {
  username: string;
  avatar: UniversalFile;
};
