"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  getCurrentUser,
  getAccessToken,
  isTokenExpired,
  refreshAccessToken,
  logout as doLogout,
  type UserInfo,
} from "@/lib/auth";

interface AuthContextType {
  user: UserInfo | null;
  loading: boolean;
  refresh: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  refresh: () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    if (isTokenExpired(token)) {
      const refreshed = await refreshAccessToken();
      if (!refreshed) {
        setUser(null);
        setLoading(false);
        return;
      }
    }

    setUser(getCurrentUser());
    setLoading(false);
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const logout = useCallback(() => {
    doLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext value={{ user, loading, refresh: loadUser, logout }}>
      {children}
    </AuthContext>
  );
}
