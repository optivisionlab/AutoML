import axiosClient from "@/api/axiosClient";

export function useApi() {
  const get = async (url: string, config = {}) => {
    const res = await axiosClient.get(url, config);
    return res.data;
  };

  // async function post(url: string, data?: any) {
  //   const res = data
  //     ? await axiosClient.post(url, data)
  //     : await axiosClient.post(url);
  //   return res.data;
  // }

  async function post(url: string, data?: any, config?: { isBlob?: boolean }) {
    const res = await axiosClient.post(url, data, {
      responseType: config?.isBlob ? "blob" : "json",
    });

    if (config?.isBlob) return res;
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
