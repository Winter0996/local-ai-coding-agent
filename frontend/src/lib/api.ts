export const API_URL = "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorBody(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);
  return body?.detail ?? `Request failed with status ${response.status}`;
}

/**
 * credentials: "include" is required on every call (not just auth ones) so
 * the browser sends/receives the httpOnly refresh-token cookie, which lives
 * at the backend's /api/auth path. Without this the refresh flow silently
 * breaks even though the request itself succeeds.
 */
export async function apiPost<T>(
  path: string,
  body: unknown,
  accessToken?: string | null,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorBody(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string, accessToken?: string | null): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(`${API_URL}${path}`, {
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorBody(response), response.status);
  }
  return (await response.json()) as T;
}
