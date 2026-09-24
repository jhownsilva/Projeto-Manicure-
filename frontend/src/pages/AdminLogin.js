import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Sparkles, Lock } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function AdminLogin() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email.trim(), password);
      toast.success("Bem-vinda!");
      navigate("/admin");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-5 py-10 bg-gradient-to-br from-[#FDF9F8] via-[#F8EFEA] to-[#FAF0D7]/40">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-2 justify-center mb-8" data-testid="login-logo-link">
          <span className="w-9 h-9 rounded-full bg-gradient-to-br from-[#D47385] to-[#C59B27] flex items-center justify-center">
            <Sparkles size={16} className="text-white" />
          </span>
          <span className="font-serif-display text-xl text-[#2A1E22] font-semibold">Studio Gel & Beauty</span>
        </Link>
        <div className="card-luxe p-8">
          <div className="flex items-center gap-2 accent-label mb-2"><Lock size={12} /> Área da profissional</div>
          <h1 className="font-serif-display text-3xl text-[#2A1E22] mb-6">Entrar no painel</h1>
          <form onSubmit={submit} className="space-y-4" data-testid="login-form">
            <div>
              <label className="block text-sm font-medium text-[#4A353D] mb-1.5">E-mail</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                data-testid="login-email"
                className="w-full rounded-xl border border-[#EADCD7] bg-white px-4 py-3 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#4A353D] mb-1.5">Senha</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                data-testid="login-password"
                className="w-full rounded-xl border border-[#EADCD7] bg-white px-4 py-3 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200" />
            </div>
            <button disabled={loading} className="btn-primary w-full disabled:opacity-50" data-testid="login-submit">
              {loading ? "Entrando..." : "Entrar"}
            </button>
          </form>
          <p className="text-xs text-[#7D636D] mt-6 text-center">Acesso restrito. Use as credenciais fornecidas ao contratar o serviço.</p>
        </div>
      </div>
    </div>
  );
}
