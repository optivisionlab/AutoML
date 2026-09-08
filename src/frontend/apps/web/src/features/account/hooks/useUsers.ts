"use client";

import {
  User,
  useGetUsersQuery,
} from "@/core/api/userApi";

export type { User };

export default function useUsers() {
  const {
    data: users = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useGetUsersQuery();

  return {
    users,
    isLoading,
    isError,
    error,
    fetchUsers: refetch,
  };
}
