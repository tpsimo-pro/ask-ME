import { ApiError } from "./client";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface TokenResponse {
  access_token: string;
}

// Auth endpoints need `credentials: "include"` so the refresh cookie is set
// and sent, and they must never carry an Authorization header — which is why
// they do not go through apiFetch.
async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, detailToMessage(payload.detail, response.statusText));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// FastAPI returns a string detail for HTTPException but an array of objects
// for 422 validation errors; flatten both into something displayable.
function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    return first?.msg ?? fallback;
  }
  return fallback;
}

export function register(name: string, email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/register", { name, email, password });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", { email, password });
}

export function forgotPassword(email: string): Promise<void> {
  return post<void>("/auth/forgot-password", { email });
}

export function resetPassword(token: string, password: string): Promise<void> {
  return post<void>("/auth/reset-password", { token, password });
}

export function logout(): Promise<void> {
  return post<void>("/auth/logout", {});
}
