import axios from "axios";
import { getSession } from "next-auth/react";

const axiosClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_BASE_API,
});

// Config cho mọi fetch
axiosClient.interceptors.request.use(async (config) => {
  const session = await getSession();

  if (session?.user.access_token) {
    config.headers.Authorization = `Bearer ${session.user.access_token}`;
  }

  if (!(config.data instanceof FormData)) {
    config.headers["Content-Type"] = "application/json";
  }

  return config;
});

export default axiosClient;
