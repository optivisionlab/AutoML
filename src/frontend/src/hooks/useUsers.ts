// useUsers gọi api lấy dữ liệu trả về

import { useState, useEffect } from "react";
import { useApi } from "./useApi";

export type User = {
  _id: string;
  username: string;
  email: string;
  password: string;
  gender: string;
  date: string;
  number: string;
  role: string;
  fullName: string;
};

export default function useUsers() {
  const { get } = useApi();
  const [users, setUsers] = useState<User[]>([]);

  const fetchUsers = async () => {
    try {
      const data = await get(`${process.env.NEXT_PUBLIC_BASE_API}/users`);
      const users = setUsers(data);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return { users, fetchUsers };
}
