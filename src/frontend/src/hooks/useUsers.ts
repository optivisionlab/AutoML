// useUsers gọi api lấy dữ liệu trả về

import { useState, useEffect } from "react";

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
  const [users, setUsers] = useState<User[]>([]);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BASE_API}/users`);
      const data = await res.json();
      setUsers(data);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return { users, fetchUsers };
}
