export const PUBLIC_ENV_KEYS = [
  "NEXT_PUBLIC_BASE_API",
  "NEXT_PUBLIC_AGENT_API",
  "NEXT_PUBLIC_TIMEOUT_CAROUSEL",
  "NEXT_PUBLIC_MQTT_URL",
  "NEXT_PUBLIC_MQTT_USERNAME",
  "NEXT_PUBLIC_MQTT_PASSWORD",
] as const;

export type PublicEnvKey = (typeof PUBLIC_ENV_KEYS)[number];
export type PublicRuntimeEnv = Partial<Record<PublicEnvKey, string>>;

declare global {
  interface Window {
    __HAUTOML_ENV__?: PublicRuntimeEnv;
  }
}

// Fallback khi chạy ngoài Docker hoặc lúc build đã có sẵn biến NEXT_PUBLIC_*.
const BUILD_TIME_PUBLIC_ENV: PublicRuntimeEnv = {
  NEXT_PUBLIC_BASE_API: process.env.NEXT_PUBLIC_BASE_API,
  NEXT_PUBLIC_AGENT_API: process.env.NEXT_PUBLIC_AGENT_API,
  NEXT_PUBLIC_TIMEOUT_CAROUSEL: process.env.NEXT_PUBLIC_TIMEOUT_CAROUSEL,
  NEXT_PUBLIC_MQTT_URL: process.env.NEXT_PUBLIC_MQTT_URL,
  NEXT_PUBLIC_MQTT_USERNAME: process.env.NEXT_PUBLIC_MQTT_USERNAME,
  NEXT_PUBLIC_MQTT_PASSWORD: process.env.NEXT_PUBLIC_MQTT_PASSWORD,
};

function readServerEnv(key: PublicEnvKey): string | undefined {
  // Đọc bằng truy cập động để Next.js/webpack không inline cố định lúc build.
  const runtimeEnv = process.env as Record<string, string | undefined>;
  return runtimeEnv[key];
}

export function getServerRuntimePublicEnv(): PublicRuntimeEnv {
  const result: PublicRuntimeEnv = {};
  for (const key of PUBLIC_ENV_KEYS) {
    const value = readServerEnv(key) ?? BUILD_TIME_PUBLIC_ENV[key];
    if (value !== undefined && value !== "") {
      result[key] = value;
    }
  }
  return result;
}

export function serializePublicEnvScript(env: PublicRuntimeEnv): string {
  const safeJson = JSON.stringify(env)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
  return `window.__HAUTOML_ENV__=${safeJson};`;
}

export function getPublicEnv(key: PublicEnvKey, fallback = ""): string {
  if (typeof window !== "undefined") {
    const runtimeValue = window.__HAUTOML_ENV__?.[key];
    if (runtimeValue !== undefined && runtimeValue !== "") {
      return runtimeValue;
    }
  } else {
    const serverValue = readServerEnv(key);
    if (serverValue !== undefined && serverValue !== "") {
      return serverValue;
    }
  }

  const buildValue = BUILD_TIME_PUBLIC_ENV[key];
  if (buildValue !== undefined && buildValue !== "") {
    return buildValue;
  }

  return fallback;
}
