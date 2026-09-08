import {
  type User,
  type UpdateUserPayload,
  type CreateUserPayload,
  type UpdateAvatarPayload,
} from "@automl/domain";
import { appendUniversalFile } from "@automl/api";
import { baseApi } from "./baseApi";

export type { User, UpdateUserPayload, CreateUserPayload, UpdateAvatarPayload };

export const userApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getUsers: builder.query<User[], void>({
      query: () => ({
        url: "/users",
      }),
      providesTags: ["User"],
    }),
    createUser: builder.mutation<unknown, CreateUserPayload>({
      query: (data) => ({
        url: "/signup",
        method: "POST",
        data,
      }),
      invalidatesTags: ["User"],
    }),
    getUser: builder.query<User, string>({
      query: (username) => ({
        url: "/users/",
        params: { username },
      }),
      providesTags: (_result, _error, username) => [
        { type: "User", id: username },
      ],
    }),
    updateUser: builder.mutation<
      unknown,
      { username: string; data: UpdateUserPayload }
    >({
      query: ({ username, data }) => ({
        url: `/update/${username}`,
        method: "PUT",
        data,
      }),
      invalidatesTags: (_result, _error, { username }) => [
        "User",
        { type: "User", id: username },
      ],
    }),
    deleteUser: builder.mutation<unknown, string>({
      query: (username) => ({
        url: `/delete/${username}`,
        method: "DELETE",
      }),
      invalidatesTags: ["User"],
    }),
    updateAvatar: builder.mutation<unknown, { username: string; avatar: File }>(
      {
        query: ({ username, avatar }) => {
          const formData = new FormData();
          appendUniversalFile(formData, "avatar", avatar);

          return {
            url: "/update_avatar",
            method: "POST",
            data: formData,
            params: { username },
          };
        },
        invalidatesTags: (_result, _error, { username }) => [
          "User",
          { type: "User", id: username },
        ],
      },
    ),
  }),
});

export const {
  useCreateUserMutation,
  useDeleteUserMutation,
  useGetUserQuery,
  useGetUsersQuery,
  useUpdateAvatarMutation,
  useUpdateUserMutation,
} = userApi;
