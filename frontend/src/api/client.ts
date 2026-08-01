const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Frontend and backend are on different origins, so the refresh cookie must
// be SameSite=None in production and is therefore sent on cross-site
// requests too -- this header is what proves the request actually came from
// our frontend (CORS only lets settings.frontend_url attach custom headers
// to a credentialed request). Must match app.auth.csrf.CSRF_HEADER_NAME /
// CSRF_HEADER_VALUE on the backend.
const CSRF_HEADER_NAME = "X-Ask-Me-Csrf";
const CSRF_HEADER_VALUE = "1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: (() => void) | null = null;

// Registered by AuthProvider so a 401 from any apiFetch call clears the
// session; AuthGuard then redirects to /login reactively once the token
// becomes null. Kept as a plain function here (not a hook) since apiFetch
// is called from outside React component bodies.
export function registerUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

let onTokenRefreshed: ((token: string) => void) | null = null;

// Registered by AuthProvider so a token obtained by a background refresh
// reaches React state.
export function registerTokenRefreshHandler(handler: (token: string) => void): void {
  onTokenRefreshed = handler;
}

export { CSRF_HEADER_NAME, CSRF_HEADER_VALUE };

let refreshPromise: Promise<string | null> | null = null;

// Every caller shares one in-flight request. Without this, parallel 401s each
// rotate the refresh token and invalidate one another, which the backend reads
// as token theft and responds to by killing every session.
export function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise === null) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { [CSRF_HEADER_NAME]: CSRF_HEADER_VALUE },
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => (body?.access_token as string | undefined) ?? null)
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {},
  allowRetry = true
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401 && allowRetry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        onTokenRefreshed?.(refreshed);
        return apiFetch<T>(path, refreshed, options, false);
      }
      onUnauthorized?.();
    }

    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  // 204 No Content (and any other empty-bodied response) has nothing to
  // parse as JSON — callers expecting no payload should use apiFetch<void>.
  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
