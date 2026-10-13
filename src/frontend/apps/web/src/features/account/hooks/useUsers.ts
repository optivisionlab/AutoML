"use client";

import {
  User,
  useGetUsersQuery,
  GetUsersParams,
} from "@/core/api/userApi";

export type { User };

export default function useUsers(params?: GetUsersParams) {
  const {
    data: response,
    isLoading,
    isError,
    error,
    refetch,
  } = useGetUsersQuery(params);

  const users: User[] = response?.data || [];
  const meta = response?.meta || {
    total_items: users.length,
    current_page: 1,
    page_size: 10,
    total_pages: 1,
  };

  return {
    users,
    meta,
    isLoading,
    isError,
    error,
    fetchUsers: refetch,
  };
}
