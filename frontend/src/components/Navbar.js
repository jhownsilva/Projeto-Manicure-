import { Link } from "react-router-dom";
import { Sparkles, Menu, X } from "lucide-react";
import { useState } from "react";

export default function Navbar({ salonName = "Studio Gel & Beauty" }) {
  const [open, setOpen] = useState(false);
  return (
    <header
      className="sticky top-0 z-40 backdrop-blur-xl border-b border-[#EADCD7]/60 bg-[#FDF9F8]/85"
      data-testid="site-navbar"
    >
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="nav-logo">
          <span className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D47385] to-[#C59B27] flex items-center justify-center">
            <Sparkles size={16} className="text-white" />
          </span>
          <span className="font-serif-display text-lg sm:text-xl text-[#2A1E22] font-semibold">
            {salonName}
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm text-[#4A353D]">
          <a href="/#servicos" data-testid="nav-services">Serviços</a>
          <a href="/#galeria" data-testid="nav-gallery">Galeria</a>
          <a href="/#contato" data-testid="nav-contact">Contato</a>
          <Link to="/agendar" className="btn-primary" data-testid="nav-book">Agendar</Link>
        </nav>
        <button
          className="md:hidden p-2 text-[#2A1E22]"
          onClick={() => setOpen((v) => !v)}
          data-testid="nav-menu-toggle"
          aria-label="Menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      {open && (
        <div className="md:hidden border-t border-[#EADCD7] bg-white/95 px-5 py-4 flex flex-col gap-3">
          <a href="/#servicos" onClick={() => setOpen(false)} data-testid="nav-services-m">Serviços</a>
          <a href="/#galeria" onClick={() => setOpen(false)} data-testid="nav-gallery-m">Galeria</a>
          <a href="/#contato" onClick={() => setOpen(false)} data-testid="nav-contact-m">Contato</a>
          <Link to="/agendar" className="btn-primary text-center" onClick={() => setOpen(false)} data-testid="nav-book-m">Agendar agora</Link>
        </div>
      )}
    </header>
  );
}
