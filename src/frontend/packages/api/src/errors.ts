export const serializeBlob = async (blob: Blob) => {
  if (blob.size === 0) return null;

  const text = await blob.text().catch(() => "");

  if (!text) {
    return blob.type
      ? `${blob.type} response (${blob.size} bytes)`
      : `Binary response (${blob.size} bytes)`;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
};

export const serializeApiErrorData = async (data: unknown) => {
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    return serializeBlob(data);
  }

  if (typeof ArrayBuffer !== "undefined" && data instanceof ArrayBuffer) {
    return `Binary response (${data.byteLength} bytes)`;
  }

  return data ?? null;
};

export const getApiErrorMessage = (error: unknown, fallback: string) => {
  if (typeof error === "object" && error !== null && "data" in error) {
    const data = (error as { data?: unknown }).data;

    if (typeof data === "string") return data;
    if (typeof data === "object" && data !== null) {
      const detail = (data as { detail?: unknown }).detail;
      const message = (data as { message?: unknown }).message;

      if (typeof detail === "string") return detail;
      if (typeof message === "string") return message;
    }
  }

  if (error instanceof Error) return error.message;

  return fallback;
};
