// src/api/publicClient.ts
import axios from "axios";

const publicClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  withCredentials: true,
});

export default publicClient;

// API public
// const res1 = await publicClient.get("/course/{id}");
