import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { API_URL, ApiError, apiGet, apiPost } from "../lib/api";

type User = {
  id: string;
  email: string;
  created_at: string;
};

type AccessTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
};

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchWithAuth: (path: string, init?: RequestInit) => Promise<Response>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // The access token lives ONLY in memory (a ref, never localStorage/
  // sessionStorage) to limit what an XSS payload could exfiltrate. A ref
  // rather than state avoids a re-render on every silent refresh and avoids
  // stale-closure bugs inside fetchWithAuth below.
  const accessTokenRef = useRef<string | null>(null);

  const fetchMe = useCallback(async (token: string) => {
    const me = await apiGet<User>("/api/auth/me", token);
    setUser(me);
  }, []);

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const data = await apiPost<AccessTokenResponse>("/api/auth/refresh", {});
      accessTokenRef.current = data.access_token;
      return data.access_token;
    } catch {
      accessTokenRef.current = null;
      setUser(null);
      return null;
    }
  }, []);

  // On first mount, try a silent refresh using whatever refresh-token cookie
  // the browser already has (if any). This is what lets a page reload skip
  // re-login without ever persisting the access token itself anywhere.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const token = await refreshAccessToken();
      if (token && !cancelled) {
        try {
          await fetchMe(token);
        } catch {
          accessTokenRef.current = null;
        }
      }
      if (!cancelled) setIsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshAccessToken, fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const data = await apiPost<AccessTokenResponse>("/api/auth/login", {
          email,
          password,
        });
        accessTokenRef.current = data.access_token;
        await fetchMe(data.access_token);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Login failed.");
        throw err;
      }
    },
    [fetchMe],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        await apiPost<User>("/api/auth/register", { email, password });
        await login(email, password);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Registration failed.");
        throw err;
      }
    },
    [login],
  );

  const logout = useCallback(async () => {
    await apiPost("/api/auth/logout", {}).catch(() => undefined);
    accessTokenRef.current = null;
    setUser(null);
  }, []);

  // Attaches the current access token and, on a 401, performs exactly one
  // silent refresh-then-retry before giving up. This covers the case where
  // the 15-minute access token expired mid-session but the refresh cookie
  // is still valid — the caller never has to think about token lifetime.
  const fetchWithAuth = useCallback(
    async (path: string, init: RequestInit = {}): Promise<Response> => {
      const doFetch = (token: string | null) =>
        fetch(`${API_URL}${path}`, {
          ...init,
          credentials: "include",
          headers: {
            ...(init.headers ?? {}),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });

      let response = await doFetch(accessTokenRef.current);

      if (response.status === 401) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          response = await doFetch(newToken);
        }
      }

      return response;
    },
    [refreshAccessToken],
  );

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    error,
    login,
    register,
    logout,
    fetchWithAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
