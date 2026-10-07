import {
  type BaseResponse,
  type ChangePasswordPayload,
  type CreateUserPayload,
  type GetUsersParams,
  type UpdateAvatarPayload,
  type UpdateUserPayload,
  type UploadAvatarResponse,
  type User,
  type UserDetailResponse,
  type UsersListResponse,
} from "@automl/domain";
import { appendUniversalFile } from "@automl/api";
import { baseApi } from "./baseApi";

export type {
  BaseResponse,
  ChangePasswordPayload,
  CreateUserPayload,
  GetUsersParams,
  UpdateAvatarPayload,
  UpdateUserPayload,
  UploadAvatarResponse,
  User,
  UserDetailResponse,
  UsersListResponse,
};

export const userApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 2.1 GET /api/v1/users (Admin Only)
    getUsers: builder.query<UsersListResponse, GetUsersParams | void>({
      query: (params) => ({
        url: "/api/v1/users",
        params: {
          page: params && "page" in params ? params.page : 1,
          page_size: params && "page_size" in params ? params.page_size : 10,
        },
      }),
      providesTags: ["User"],
    }),

    // Admin Create User
    createUser: builder.mutation<BaseResponse<User>, CreateUserPayload | any>({
      query: (data) => ({
        url: "/api/v1/auth/signup",
        method: "POST",
        data,
      }),
      invalidatesTags: ["User"],
    }),

    // 2.2 GET /api/v1/users/{id}
    getUser: builder.query<UserDetailResponse, string>({
      query: (id) => ({
        url: `/api/v1/users/${id}`,
      }),
      providesTags: (_result, _error, id) => [{ type: "User", id }],
    }),

    // 2.3 PUT /api/v1/users/{id}
    updateUser: builder.mutation<
      UserDetailResponse,
      { id: string; data: UpdateUserPayload } | { username?: string; data: UpdateUserPayload; id?: string }
    >({
      query: (arg) => {
        const userId = (arg as any).id || (arg as any).username;
        return {
          url: `/api/v1/users/${userId}`,
          method: "PUT",
          data: arg.data,
        };
      },
      invalidatesTags: (_result, _error, arg) => {
        const userId = (arg as any).id || (arg as any).username;
        return ["User", "Auth", { type: "User", id: userId }];
      },
    }),

    // 2.4 DELETE /api/v1/users/{id} (Admin Only)
    deleteUser: builder.mutation<BaseResponse<null>, string>({
      query: (id) => ({
        url: `/api/v1/users/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["User"],
    }),

    // 2.6 POST /api/v1/users/{id}/avatar
    updateAvatar: builder.mutation<
      UploadAvatarResponse,
      { id?: string; username?: string; avatar: File | Blob }
    >({
      query: ({ id, username, avatar }) => {
        const targetId = id || username || "";
        const formData = new FormData();
        appendUniversalFile(formData, "file", avatar);

        return {
          url: `/api/v1/users/${targetId}/avatar`,
          method: "POST",
          data: formData,
        };
      },
      invalidatesTags: (_result, _error, { id, username }) => [
        "User",
        "Auth",
        { type: "User", id: id || username },
      ],
    }),

    // 2.7 POST /api/v1/users/{id}/password
    changeUserPassword: builder.mutation<
      BaseResponse<null>,
      { id: string; payload: ChangePasswordPayload }
    >({
      query: ({ id, payload }) => ({
        url: `/api/v1/users/${id}/password`,
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Auth"],
    }),
  }),
});

export const {
  useChangeUserPasswordMutation,
  useCreateUserMutation,
  useDeleteUserMutation,
  useGetUserQuery,
  useGetUsersQuery,
  useLazyGetUserQuery,
  useLazyGetUsersQuery,
  useUpdateAvatarMutation,
  useUpdateUserMutation,
} = userApi;
