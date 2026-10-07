import { AxiosInstance } from "axios";
import {
  BaseResponse,
  ChangePasswordPayload,
  GetUsersParams,
  UniversalFile,
  UpdateUserPayload,
  UploadAvatarResponse,
  User,
  UserDetailResponse,
  UsersListResponse,
} from "@automl/domain";
import { appendUniversalFile } from "../form-data";

export const createUserService = (client: AxiosInstance) => ({
  // 2.1 GET /api/v1/users (Admin Only)
  getUsers: async (params?: GetUsersParams): Promise<UsersListResponse> => {
    const res = await client.get<UsersListResponse>("/api/v1/users", {
      params: {
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 10,
      },
    });
    return res.data;
  },

  // 2.2 GET /api/v1/users/{id}
  getUserById: async (id: string): Promise<UserDetailResponse> => {
    const res = await client.get<UserDetailResponse>(`/api/v1/users/${id}`);
    return res.data;
  },

  // 2.3 PUT /api/v1/users/{id}
  updateUser: async (
    id: string,
    data: UpdateUserPayload,
  ): Promise<UserDetailResponse> => {
    const res = await client.put<UserDetailResponse>(`/api/v1/users/${id}`, data);
    return res.data;
  },

  // 2.4 DELETE /api/v1/users/{id} (Admin Only)
  deleteUser: async (id: string): Promise<BaseResponse<null>> => {
    const res = await client.delete<BaseResponse<null>>(`/api/v1/users/${id}`);
    return res.data;
  },

  // 2.5 GET /api/v1/users/{id}/avatar
  getAvatar: async (id: string): Promise<Blob> => {
    const res = await client.get(`/api/v1/users/${id}/avatar`, {
      responseType: "blob",
    });
    return res.data;
  },

  // 2.6 POST /api/v1/users/{id}/avatar
  uploadAvatar: async (
    id: string,
    file: UniversalFile,
  ): Promise<UploadAvatarResponse> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file", file);

    const res = await client.post<UploadAvatarResponse>(
      `/api/v1/users/${id}/avatar`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return res.data;
  },

  // 2.7 POST /api/v1/users/{id}/password
  changePassword: async (
    id: string,
    payload: ChangePasswordPayload,
  ): Promise<BaseResponse<null>> => {
    const res = await client.post<BaseResponse<null>>(
      `/api/v1/users/${id}/password`,
      payload,
    );
    return res.data;
  },

  // Legacy method compatibility
  getUser: async (identifier: string): Promise<User> => {
    const res = await client.get<UserDetailResponse>(`/api/v1/users/${identifier}`);
    return (res.data.data || res.data) as User;
  },
  createUser: async (data: any): Promise<unknown> => {
    const res = await client.post("/api/v1/auth/signup", data);
    return res.data;
  },
  updateAvatar: async ({ username, avatar, userId }: any): Promise<unknown> => {
    const id = userId || username;
    const formData = new FormData();
    appendUniversalFile(formData, "file", avatar);
    const res = await client.post(`/api/v1/users/${id}/avatar`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },
});
