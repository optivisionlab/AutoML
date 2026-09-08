import { AxiosInstance } from "axios";
import {
  CreateUserPayload,
  UpdateAvatarPayload,
  UpdateUserPayload,
  User,
} from "@automl/domain";
import { appendUniversalFile } from "../form-data";

export const createUserService = (client: AxiosInstance) => ({
  getUsers: async (): Promise<User[]> => {
    const res = await client.get<User[]>("/users");
    return res.data;
  },

  createUser: async (data: CreateUserPayload): Promise<unknown> => {
    const res = await client.post("/signup", data);
    return res.data;
  },

  getUser: async (username: string): Promise<User> => {
    const res = await client.get<User>("/users/", {
      params: { username },
    });
    return res.data;
  },

  updateUser: async (username: string, data: UpdateUserPayload): Promise<unknown> => {
    const res = await client.put(`/update/${username}`, data);
    return res.data;
  },

  deleteUser: async (username: string): Promise<unknown> => {
    const res = await client.delete(`/delete/${username}`);
    return res.data;
  },

  updateAvatar: async ({ username, avatar }: UpdateAvatarPayload): Promise<unknown> => {
    const formData = new FormData();
    appendUniversalFile(formData, "avatar", avatar);

    const res = await client.post("/update_avatar", formData, {
      params: { username },
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },
});
