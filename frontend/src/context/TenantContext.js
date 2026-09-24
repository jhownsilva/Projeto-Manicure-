import { createContext, useContext, useEffect, useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { api } from "@/lib/api";

const TenantContext = createContext(null);

export function TenantShell() {
  const { slug } = useParams();
  const key = slug || "default";
  const base = slug ? `/s/${slug}` : "";
  const [salon, setSalon] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setSalon(null); setError(false);
    api.get(`/public/${key}/salon`).then((r) => setSalon(r.data)).catch(() => setError(true));
  }, [key]);

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6" data-testid="tenant-not-found">
        <h1 className="font-serif-display text-3xl text-[#2A1E22] mb-2">Salão não encontrado</h1>
        <p className="text-[#6E555E]">Verifique o endereço e tente novamente.</p>
      </div>
    );
  }
  if (!salon) return <div className="min-h-screen flex items-center justify-center text-[#6E555E]">Carregando...</div>;

  return (
    <TenantContext.Provider value={{ slug: key, base, salon }}>
      <Outlet />
    </TenantContext.Provider>
  );
}

export const useTenant = () => useContext(TenantContext);
