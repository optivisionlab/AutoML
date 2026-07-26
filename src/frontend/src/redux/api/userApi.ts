import { baseApi } from "./baseApi";

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
          formData.append("avatar", avatar);

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
