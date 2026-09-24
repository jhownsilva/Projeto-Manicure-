import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Landing from "@/pages/Landing";
import Booking from "@/pages/Booking";
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";
import "@/App.css";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-[#6E555E]">Carregando...</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/agendar" element={<Booking />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<Protected><AdminDashboard /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
