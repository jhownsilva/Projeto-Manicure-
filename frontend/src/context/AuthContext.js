import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anonymous, obj = logged in
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { check(); }, [check]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    if (data?.token) localStorage.setItem("access_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("access_token");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh: check }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
