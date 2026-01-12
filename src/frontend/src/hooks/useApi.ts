import axiosClient from "@/api/axiosClient";

export function useApi() {
  async function get(url: string) {
    const res = await axiosClient.get(url);
    return res.data;
  }

  async function post(url: string, data?: any) {
    const res = data
      ? await axiosClient.post(url, data)
      : await axiosClient.post(url);
    return res.data;
  }

  async function put(url: string, data: any) {
    const res = await axiosClient.put(url, data);
    return res.data;
  }

  async function remove(url: string) {
    const res = await axiosClient.delete(url);
    return res.data;
  }

  return { get, post, put, remove };
}
