const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

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

export async function apiFetch<T>(
  path: string,
  token: string | null,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    if (response.status === 401) {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  return response.json() as Promise<T>;
}
