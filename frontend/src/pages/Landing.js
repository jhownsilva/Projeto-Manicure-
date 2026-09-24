import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Sparkles, Clock, Star, MapPin, Instagram, Phone } from "lucide-react";
import Navbar from "@/components/Navbar";
import WhatsAppFab from "@/components/WhatsAppFab";
import PWAInstall from "@/components/PWAInstall";
import { api } from "@/lib/api";

const GALLERY = [
  "https://images.unsplash.com/photo-1610992015762-45dca7fa3a85?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NjZ8MHwxfHNlYXJjaHwyfHxnZWwlMjBuYWlscyUyMG1hbmljdXJlJTIwc2Fsb24lMjBsdXh1cnl8ZW58MHx8fHwxNzkwMjg4MDI0fDA&ixlib=rb-4.1.0&q=85",
  "https://images.pexels.com/photos/38784151/pexels-photo-38784151.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
  "https://images.pexels.com/photos/3997381/pexels-photo-3997381.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
  "https://images.pexels.com/photos/34885842/pexels-photo-34885842.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
];

const HERO_IMG = "https://images.unsplash.com/photo-1610992015762-45dca7fa3a85?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NjZ8MHwxfHNlYXJjaHwyfHxnZWwlMjBuYWlscyUyMG1hbmljdXJlJTIwc2Fsb24lMjBsdXh1cnl8ZW58MHx8fHwxNzkwMjg4MDI0fDA&ixlib=rb-4.1.0&q=85";

export default function Landing() {
  const [services, setServices] = useState([]);
  const [salon, setSalon] = useState({ name: "Studio Gel & Beauty", whatsapp: "5511999999999" });

  useEffect(() => {
    api.get("/services").then((r) => setServices(r.data)).catch(() => {});
    api.get("/salon").then((r) => setSalon(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen">
      <Navbar salonName={salon.name} />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 pt-10 sm:pt-16 pb-16 grid lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6 space-y-6">
            <span className="accent-label" data-testid="hero-eyebrow">Estúdio de manicure em gel</span>
            <h1 className="font-serif-display text-4xl sm:text-5xl lg:text-6xl font-semibold leading-[1.05] text-[#2A1E22]">
              Unhas que <span className="italic text-[#C59B27]">brilham</span>,<br />
              autoestima que <span className="text-[#D47385]">encanta</span>.
            </h1>
            <p className="text-[#5C454E] text-base sm:text-lg leading-relaxed max-w-lg">
              Um cuidado premium para suas mãos, com finalização em gel de longa duração.
              Agende em 3 passos, direto do seu celular.
            </p>
            <div className="flex flex-wrap gap-3 items-center">
              <Link to="/agendar" data-testid="hero-book-btn" className="btn-primary inline-flex items-center gap-2">
                <Sparkles size={16} /> Agendar meu horário
              </Link>
              <a href="#servicos" className="btn-ghost" data-testid="hero-services-btn">Ver serviços</a>
            </div>
            <div className="flex items-center gap-6 pt-4">
              <div className="flex items-center gap-2 text-sm text-[#4A353D]">
                <Star size={16} className="text-[#C59B27] fill-[#C59B27]" /> 4.9 (312 avaliações)
              </div>
              <div className="flex items-center gap-2 text-sm text-[#4A353D]">
                <Clock size={16} className="text-[#D47385]" /> Seg–Sáb · 9h às 19h
              </div>
            </div>
          </div>
          <div className="lg:col-span-6 relative">
            <div className="relative rounded-[2rem] overflow-hidden shadow-[0_25px_60px_rgba(212,115,133,0.18)]">
              <img src={HERO_IMG} alt="Manicure em gel" className="w-full h-[420px] sm:h-[520px] object-cover" />
              <div className="absolute bottom-5 left-5 bg-white/90 backdrop-blur-md rounded-2xl px-4 py-3 border border-[#EADCD7]">
                <div className="text-xs uppercase tracking-wider text-[#B38059] font-semibold">Próximo horário</div>
                <div className="font-serif-display text-lg text-[#2A1E22]">Hoje · 15h30</div>
              </div>
              <div className="absolute top-5 right-5 chip">
                <Sparkles size={12} /> Gel Premium
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="gold-divider max-w-3xl mx-auto" />

      {/* Services */}
      <section id="servicos" className="max-w-6xl mx-auto px-5 sm:px-8 py-16 sm:py-24">
        <div className="flex items-end justify-between flex-wrap gap-4 mb-10">
          <div>
            <span className="accent-label">Cardápio</span>
            <h2 className="font-serif-display text-3xl sm:text-4xl font-medium text-[#2A1E22] mt-2">
              Serviços & preços
            </h2>
          </div>
          <Link to="/agendar" className="btn-ghost" data-testid="services-cta">Escolher e agendar</Link>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="services-grid">
          {services.map((s) => (
            <article key={s.id} className="card-luxe overflow-hidden" data-testid={`service-card-${s.id}`}>
              {s.image_url && (
                <div className="h-44 w-full overflow-hidden">
                  <img src={s.image_url} alt={s.name} className="w-full h-full object-cover transition-transform duration-500 hover:scale-105" />
                </div>
              )}
              <div className="p-6 space-y-3">
                <h3 className="font-serif-display text-xl text-[#2A1E22]">{s.name}</h3>
                <p className="text-sm text-[#6E555E] leading-relaxed min-h-[40px]">{s.description}</p>
                <div className="flex items-center justify-between pt-2">
                  <div className="flex items-center gap-2 text-sm text-[#4A353D]">
                    <Clock size={14} /> {Math.floor(s.duration_min/60) ? `${Math.floor(s.duration_min/60)}h ` : ""}{s.duration_min % 60 ? `${s.duration_min%60}min` : ""}
                  </div>
                  <div className="font-serif-display text-xl text-[#C59B27] font-semibold">
                    R$ {s.price.toFixed(2).replace(".", ",")}
                  </div>
                </div>
                <Link
                  to={`/agendar?service=${s.id}`}
                  className="btn-primary w-full inline-flex items-center justify-center mt-2"
                  data-testid={`book-service-btn-${s.id}`}
                >
                  Agendar {s.name.split(" ")[0]}
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Gallery */}
      <section id="galeria" className="bg-[#F8EFEA]/70 py-16 sm:py-24">
        <div className="max-w-6xl mx-auto px-5 sm:px-8">
          <div className="mb-10">
            <span className="accent-label">Portfólio</span>
            <h2 className="font-serif-display text-3xl sm:text-4xl font-medium text-[#2A1E22] mt-2">
              Trabalhos que falam por si
            </h2>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {GALLERY.map((src, i) => (
              <div key={i} className="rounded-2xl overflow-hidden aspect-[3/4] shadow-md border border-[#EADCD7]" data-testid={`gallery-img-${i}`}>
                <img src={src} alt={`Trabalho ${i+1}`} className="w-full h-full object-cover transition-transform duration-500 hover:scale-105" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact */}
      <section id="contato" className="max-w-6xl mx-auto px-5 sm:px-8 py-16 sm:py-24 grid md:grid-cols-2 gap-10">
        <div className="space-y-5">
          <span className="accent-label">Contato</span>
          <h2 className="font-serif-display text-3xl sm:text-4xl font-medium text-[#2A1E22]">
            Vem se cuidar com a gente
          </h2>
          <p className="text-[#5C454E]">Atendimento com hora marcada em um ambiente acolhedor e higienizado.</p>
          <ul className="space-y-3 text-[#4A353D]">
            <li className="flex items-center gap-3"><MapPin size={18} className="text-[#D47385]" /> Rua das Flores, 123 · São Paulo · SP</li>
            <li className="flex items-center gap-3"><Phone size={18} className="text-[#D47385]" /> (11) 99999-9999</li>
            <li className="flex items-center gap-3"><Instagram size={18} className="text-[#D47385]" /> @studiogelbeauty</li>
            <li className="flex items-center gap-3"><Clock size={18} className="text-[#D47385]" /> Seg a Sáb · 09h às 19h</li>
          </ul>
          <Link to="/agendar" className="btn-primary inline-flex items-center gap-2" data-testid="contact-book-btn">
            <Sparkles size={16} /> Agendar horário
          </Link>
        </div>
        <div className="card-luxe p-8">
          <span className="accent-label">Depoimento</span>
          <blockquote className="font-serif-display text-2xl text-[#2A1E22] italic mt-4 leading-snug">
            “Nunca tinha visto minhas unhas tão bonitas. O acabamento em gel dura semanas e o atendimento é impecável.”
          </blockquote>
          <div className="mt-6 flex items-center gap-3">
            <img src="https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=200" alt="Cliente" className="w-12 h-12 rounded-full object-cover border border-[#E2C889]" />
            <div>
              <div className="text-sm font-semibold text-[#2A1E22]">Marina S.</div>
              <div className="text-xs text-[#7D636D]">Cliente desde 2024</div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#EADCD7] py-8 text-center text-sm text-[#7D636D]">
        © {new Date().getFullYear()} {salon.name} · Feito com carinho · <Link to="/admin/login" className="text-[#B38059] hover:underline" data-testid="footer-admin-link">Área da profissional</Link>
      </footer>

      <WhatsAppFab phone={salon.whatsapp} />
      <PWAInstall />
    </div>
  );
}
