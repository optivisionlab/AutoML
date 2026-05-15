import { NextRequest, NextResponse } from "next/server";

type RouteContext = {
  params:
    | {
        path?: string[];
      }
    | Promise<{
        path?: string[];
      }>;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function getHAgentInternalURL(): string | null {
  const configuredURL = process.env.HAGENT_INTERNAL_URL?.trim();
  return configuredURL ? configuredURL.replace(/\/$/, "") : null;
}

function filterProxyHeaders(headers: Headers): Headers {
  const nextHeaders = new Headers(headers);

  HOP_BY_HOP_HEADERS.forEach((header) => {
    nextHeaders.delete(header);
  });

  return nextHeaders;
}

async function proxyHAgent(request: NextRequest, context: RouteContext) {
  const hagentBaseURL = getHAgentInternalURL();

  if (!hagentBaseURL) {
    return NextResponse.json(
      {
        detail: "HAGENT_INTERNAL_URL is not configured for the frontend server.",
      },
      { status: 503 }
    );
  }

  const params = await Promise.resolve(context.params);
  const path = (params.path ?? []).map(encodeURIComponent).join("/");
  // Preserve trailing slash from original request to avoid 307 redirects from FastAPI
  const trailingSlash = request.nextUrl.pathname.endsWith("/") ? "/" : "";
  const targetURL = new URL(`${hagentBaseURL}/${path}${trailingSlash}`);
  targetURL.search = request.nextUrl.search;

  const requestInit: RequestInit = {
    method: request.method,
    headers: filterProxyHeaders(request.headers),
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    requestInit.body = await request.arrayBuffer();
  }

  try {
    let response = await fetch(targetURL, requestInit);

    // If bridge returns 3xx redirect (e.g., FastAPI trailing-slash 307),
    // follow it internally using the internal base URL to avoid cross-origin browser redirect.
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location");
      if (location) {
        try {
          const locURL = new URL(location);
          const redirectURL = new URL(`${hagentBaseURL}${locURL.pathname}`);
          redirectURL.search = locURL.search;
          response = await fetch(redirectURL, { ...requestInit, redirect: "manual" });
        } catch {
          // fall through — return original redirect response to browser
        }
      }
    }

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: filterProxyHeaders(response.headers),
    });
  } catch {
    return NextResponse.json(
      {
        detail: "Cannot connect to HAgent Bridge from the frontend server.",
      },
      { status: 502 }
    );
  }
}

export const GET = proxyHAgent;
export const POST = proxyHAgent;
export const DELETE = proxyHAgent;
export const OPTIONS = proxyHAgent;
