import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Calendar, Users, DollarSign, Clock, LogOut, Plus, Trash2, Edit3,
  Ban, Sparkles, CheckCircle2, XCircle, Bell, Settings, Building2, ShieldCheck
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import SettingsTab from "@/components/admin/SettingsTab";
import TenantsTab from "@/components/admin/TenantsTab";
import RemindersTab from "@/components/admin/RemindersTab";

const TABS = [
  { id: "agenda", label: "Agenda", icon: Calendar },
  { id: "servicos", label: "Serviços", icon: Sparkles },
  { id: "bloqueios", label: "Bloqueios", icon: Ban },
  { id: "clientes", label: "Clientes", icon: Users },
  { id: "lembretes", label: "Lembretes", icon: Bell },
  { id: "config", label: "Configurações", icon: Settings },
  { id: "saloes", label: "Salões", icon: Building2, superadmin: true },
];

function ymd(d) {
  const y = d.getFullYear(); const m = String(d.getMonth() + 1).padStart(2, "0"); const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function AdminDashboard() {
  const { user, logout, refresh } = useAuth();
  const [tab, setTab] = useState("agenda");
  const [stats, setStats] = useState(null);
  const [range, setRange] = useState("today"); // today | week | month
  const [bookings, setBookings] = useState([]);
  const [services, setServices] = useState([]);
  const [clients, setClients] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const isSuper = user?.role === "superadmin";
  const activeSlug = user?.tenant?.slug;

  const switchTenant = async (slug) => {
    localStorage.setItem("active_tenant", slug);
    await refresh();
    loadStats();
    setTab("agenda");
    toast.success("Salão alterado");
  };

  const loadStats = () => api.get("/stats").then((r) => setStats(r.data)).catch((e) => toast.error(formatApiError(e)));
  const loadBookings = () => {
    const today = new Date();
    let from, to;
    if (range === "today") { from = ymd(today); to = ymd(today); }
    else if (range === "week") {
      const start = new Date(today); start.setDate(today.getDate() - today.getDay());
      const end = new Date(start); end.setDate(start.getDate() + 6);
      from = ymd(start); to = ymd(end);
    } else {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      from = ymd(start); to = ymd(end);
    }
    return api.get("/bookings", { params: { from_date: from, to_date: to } })
      .then((r) => setBookings(r.data)).catch((e) => toast.error(formatApiError(e)));
  };
  const loadServices = () => api.get("/services", { params: { all: true } }).then((r) => setServices(r.data));
  const loadClients = () => api.get("/clients").then((r) => setClients(r.data));
  const loadBlocks = () => api.get("/blocks").then((r) => setBlocks(r.data));

  useEffect(() => { loadStats(); }, [activeSlug]);
  useEffect(() => { if (tab === "agenda") loadBookings(); }, [tab, range, activeSlug]);
  useEffect(() => {
    if (tab === "servicos") loadServices();
    if (tab === "clientes") loadClients();
    if (tab === "bloqueios") loadBlocks();
  }, [tab, activeSlug]);

  return (
    <div className="min-h-screen bg-[#FDF9F8]">
      <header className="bg-white/80 backdrop-blur-xl border-b border-[#EADCD7] sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D47385] to-[#C59B27] flex items-center justify-center">
              <Sparkles size={16} className="text-white" />
            </span>
            <div>
              <div className="font-serif-display text-lg text-[#2A1E22] font-semibold leading-tight" data-testid="admin-salon-name">{user?.tenant?.name || "Painel Admin"}</div>
              <div className="text-xs text-[#7D636D]">Olá, {user?.name?.split(" ")[0]}{isSuper && " · Super-admin"}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSuper && user?.tenants?.length > 0 && (
              <select value={activeSlug || ""} onChange={(e) => switchTenant(e.target.value)} data-testid="tenant-switcher"
                className="rounded-full border border-[#EADCD7] bg-white px-3 py-2 text-sm text-[#2A1E22] focus:border-[#D47385] focus:outline-none">
                {user.tenants.map((t) => <option key={t.id} value={t.slug}>{t.name}</option>)}
              </select>
            )}
            <button onClick={logout} data-testid="logout-btn" className="btn-ghost inline-flex items-center gap-2 text-sm">
              <LogOut size={14} /> Sair
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 sm:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8" data-testid="stats-cards">
          <StatCard icon={Calendar} label="Hoje" value={stats?.today ?? "—"} color="#D47385" testId="stat-today" />
          <StatCard icon={Clock} label="Esta semana" value={stats?.week ?? "—"} color="#B38059" testId="stat-week" />
          <StatCard icon={DollarSign} label="Faturamento mês" value={stats ? `R$ ${stats.month_revenue.toFixed(2).replace(".", ",")}` : "—"} color="#C59B27" testId="stat-revenue" />
          <StatCard icon={ShieldCheck} label="Sinais recebidos" value={stats ? `R$ ${(stats.deposits_month || 0).toFixed(2).replace(".", ",")}` : "—"} color="#6B478C" testId="stat-deposits" />
          <StatCard icon={Users} label="Clientes" value={stats?.clients ?? "—"} color="#2E7D32" testId="stat-clients" />
        </div>

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto mb-6 pb-1" data-testid="admin-tabs">
          {TABS.filter((t) => !t.superadmin || isSuper).map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
              className={`flex-shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-colors duration-200 ${
                tab === t.id ? "bg-[#2A1E22] text-white" : "bg-white border border-[#EADCD7] text-[#4A353D] hover:border-[#D47385]"
              }`}>
              <t.icon size={14} /> {t.label}
            </button>
          ))}
        </div>

        {tab === "agenda" && <AgendaTab range={range} setRange={setRange} bookings={bookings} reload={() => { loadBookings(); loadStats(); }} />}
        {tab === "servicos" && <ServicesTab services={services} reload={loadServices} />}
        {tab === "bloqueios" && <BlocksTab blocks={blocks} reload={loadBlocks} />}
        {tab === "clientes" && <ClientsTab clients={clients} />}
        {tab === "lembretes" && <RemindersTab key={activeSlug} />}
        {tab === "config" && <SettingsTab key={activeSlug} onSaved={refresh} />}
        {tab === "saloes" && isSuper && <TenantsTab onChanged={refresh} />}
      </main>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, testId }) {
  return (
    <div className="card-luxe p-5" data-testid={testId}>
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-full flex items-center justify-center" style={{ backgroundColor: `${color}22`, color }}>
          <Icon size={18} />
        </span>
        <div className="text-xs uppercase tracking-wider text-[#7D636D] font-semibold">{label}</div>
      </div>
      <div className="mt-3 font-serif-display text-2xl text-[#2A1E22]">{value}</div>
    </div>
  );
}

function statusChip(status) {
  const map = {
    pending: { label: "Aguardando", bg: "#FAF0D7", color: "#B38059" },
    confirmed: { label: "Confirmado", bg: "#E4F4E5", color: "#2E7D32" },
    cancelled: { label: "Cancelado", bg: "#FBE4E4", color: "#B02A2A" },
    completed: { label: "Concluído", bg: "#F0E7F6", color: "#6B478C" },
  };
  const s = map[status] || map.pending;
  return <span className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ backgroundColor: s.bg, color: s.color }}>{s.label}</span>;
}

function AgendaTab({ range, setRange, bookings, reload }) {
  const changeStatus = async (id, status) => {
    try { await api.put(`/bookings/${id}/status`, { status }); toast.success("Status atualizado"); reload(); }
    catch (e) { toast.error(formatApiError(e)); }
  };
  const grouped = useMemo(() => {
    const m = {};
    bookings.forEach((b) => { (m[b.date] ||= []).push(b); });
    return Object.entries(m).sort(([a],[b]) => a.localeCompare(b));
  }, [bookings]);

  return (
    <div>
      <div className="flex items-center gap-2 mb-5">
        {["today","week","month"].map((r) => (
          <button key={r} onClick={() => setRange(r)} data-testid={`range-${r}`}
            className={`px-4 py-1.5 rounded-full text-sm transition-colors duration-200 ${range === r ? "bg-[#D47385] text-white" : "bg-white border border-[#EADCD7] text-[#4A353D]"}`}>
            {r === "today" ? "Hoje" : r === "week" ? "Semana" : "Mês"}
          </button>
        ))}
      </div>

      {grouped.length === 0 ? (
        <div className="card-luxe p-10 text-center text-[#7D636D]" data-testid="agenda-empty">Nenhum agendamento neste período.</div>
      ) : (
        <div className="space-y-6" data-testid="agenda-list">
          {grouped.map(([date, items]) => (
            <div key={date}>
              <div className="accent-label mb-3">
                {new Date(date + "T00:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}
              </div>
              <div className="space-y-2">
                {items.map((b) => (
                  <div key={b.id} className="card-luxe p-4 flex flex-col sm:flex-row sm:items-center gap-3" data-testid={`booking-row-${b.id}`}>
                    <div className="font-serif-display text-2xl text-[#C59B27] w-20">{b.time}</div>
                    <div className="flex-1">
                      <div className="text-[#2A1E22] font-semibold">{b.client_name}</div>
                      <div className="text-sm text-[#6E555E]">{b.service_name} · R$ {b.service_price.toFixed(2).replace(".", ",")} · {b.service_duration} min</div>
                      <div className="text-xs text-[#7D636D] mt-1">{b.client_phone}</div>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {b.deposit_status === "paid" && (
                        <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-[#F0E7F6] text-[#6B478C] inline-flex items-center gap-1" data-testid={`deposit-paid-${b.id}`}>
                          <ShieldCheck size={12} /> Sinal R$ {Number(b.deposit_amount || 0).toFixed(2).replace(".", ",")}
                        </span>
                      )}
                      {statusChip(b.status)}
                      {b.status !== "confirmed" && b.status !== "cancelled" && (
                        <button onClick={() => changeStatus(b.id, "confirmed")} data-testid={`confirm-${b.id}`} title="Confirmar" className="p-2 rounded-full hover:bg-[#E4F4E5] text-[#2E7D32]"><CheckCircle2 size={18} /></button>
                      )}
                      {b.status !== "cancelled" && (
                        <button onClick={() => changeStatus(b.id, "cancelled")} data-testid={`cancel-${b.id}`} title="Cancelar" className="p-2 rounded-full hover:bg-[#FBE4E4] text-[#B02A2A]"><XCircle size={18} /></button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ServicesTab({ services, reload }) {
  const empty = { name: "", description: "", price: "", duration_min: "", image_url: "", active: true };
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);

  const openNew = () => { setEditing("new"); setForm(empty); };
  const openEdit = (s) => { setEditing(s.id); setForm({ ...s, price: String(s.price), duration_min: String(s.duration_min) }); };
  const save = async () => {
    const payload = { ...form, price: Number(form.price), duration_min: Number(form.duration_min) };
    if (!payload.name || !payload.price || !payload.duration_min) { toast.error("Preencha nome, preço e duração."); return; }
    try {
      if (editing === "new") await api.post("/services", payload);
      else await api.put(`/services/${editing}`, payload);
      toast.success("Serviço salvo"); setEditing(null); reload();
    } catch (e) { toast.error(formatApiError(e)); }
  };
  const remove = async (id) => {
    if (!window.confirm("Excluir este serviço?")) return;
    try { await api.delete(`/services/${id}`); toast.success("Excluído"); reload(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={openNew} className="btn-primary inline-flex items-center gap-2" data-testid="new-service-btn"><Plus size={14} /> Novo serviço</button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((s) => (
          <div key={s.id} className="card-luxe p-5" data-testid={`service-item-${s.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-serif-display text-lg text-[#2A1E22]">{s.name}</div>
                <div className="text-sm text-[#6E555E]">R$ {s.price.toFixed(2).replace(".", ",")} · {s.duration_min} min</div>
                {!s.active && <div className="text-xs mt-1 text-[#B02A2A]">Inativo</div>}
              </div>
              <div className="flex gap-1">
                <button onClick={() => openEdit(s)} data-testid={`edit-service-${s.id}`} className="p-2 rounded-full hover:bg-[#FCEEEF] text-[#B38059]"><Edit3 size={16} /></button>
                <button onClick={() => remove(s.id)} data-testid={`delete-service-${s.id}`} className="p-2 rounded-full hover:bg-[#FBE4E4] text-[#B02A2A]"><Trash2 size={16} /></button>
              </div>
            </div>
            <p className="text-sm text-[#6E555E] mt-2 leading-relaxed">{s.description}</p>
          </div>
        ))}
      </div>

      {editing && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setEditing(null)}>
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-3" onClick={(e) => e.stopPropagation()} data-testid="service-modal">
            <h3 className="font-serif-display text-2xl text-[#2A1E22]">{editing === "new" ? "Novo serviço" : "Editar serviço"}</h3>
            <ModalField label="Nome" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="service-name" />
            <ModalField label="Descrição" value={form.description} onChange={(v) => setForm({ ...form, description: v })} testId="service-desc" />
            <div className="grid grid-cols-2 gap-3">
              <ModalField label="Preço (R$)" value={form.price} onChange={(v) => setForm({ ...form, price: v })} testId="service-price" />
              <ModalField label="Duração (min)" value={form.duration_min} onChange={(v) => setForm({ ...form, duration_min: v })} testId="service-duration" />
            </div>
            <ModalField label="URL da imagem" value={form.image_url} onChange={(v) => setForm({ ...form, image_url: v })} testId="service-image" />
            <label className="flex items-center gap-2 text-sm text-[#4A353D]">
              <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} data-testid="service-active" />
              Ativo (visível para clientes)
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditing(null)} className="btn-ghost" data-testid="service-cancel">Cancelar</button>
              <button onClick={save} className="btn-primary" data-testid="service-save">Salvar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ModalField({ label, value, onChange, testId }) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-[#7D636D] font-semibold mb-1">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}
        className="w-full rounded-xl border border-[#EADCD7] bg-white px-3 py-2 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200" />
    </div>
  );
}

function BlocksTab({ blocks, reload }) {
  const [form, setForm] = useState({ date: ymd(new Date()), time: "", reason: "" });
  const create = async () => {
    try {
      await api.post("/blocks", { date: form.date, time: form.time || null, reason: form.reason });
      toast.success("Bloqueio criado"); setForm({ date: ymd(new Date()), time: "", reason: "" }); reload();
    } catch (e) { toast.error(formatApiError(e)); }
  };
  const remove = async (id) => {
    try { await api.delete(`/blocks/${id}`); toast.success("Removido"); reload(); }
    catch (e) { toast.error(formatApiError(e)); }
  };
  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="card-luxe p-6" data-testid="new-block-card">
        <h3 className="font-serif-display text-xl text-[#2A1E22] mb-4">Novo bloqueio</h3>
        <div className="space-y-3">
          <ModalField label="Data" value={form.date} onChange={(v) => setForm({ ...form, date: v })} testId="block-date" />
          <ModalField label="Horário (opcional, HH:MM). Vazio = dia inteiro" value={form.time} onChange={(v) => setForm({ ...form, time: v })} testId="block-time" />
          <ModalField label="Motivo" value={form.reason} onChange={(v) => setForm({ ...form, reason: v })} testId="block-reason" />
          <button onClick={create} className="btn-primary" data-testid="save-block-btn">Bloquear</button>
        </div>
      </div>
      <div>
        <h3 className="font-serif-display text-xl text-[#2A1E22] mb-4">Bloqueios ativos</h3>
        <div className="space-y-2">
          {blocks.length === 0 && <div className="text-sm text-[#7D636D]">Nenhum bloqueio configurado.</div>}
          {blocks.map((b) => (
            <div key={b.id} className="card-luxe p-4 flex items-center justify-between" data-testid={`block-row-${b.id}`}>
              <div>
                <div className="text-[#2A1E22] font-semibold">
                  {b.date.split("-").reverse().join("/")} {b.time ? `· ${b.time}` : "· dia inteiro"}
                </div>
                {b.reason && <div className="text-xs text-[#7D636D]">{b.reason}</div>}
              </div>
              <button onClick={() => remove(b.id)} data-testid={`delete-block-${b.id}`} className="p-2 rounded-full hover:bg-[#FBE4E4] text-[#B02A2A]"><Trash2 size={16} /></button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ClientsTab({ clients }) {
  return (
    <div>
      {clients.length === 0 && <div className="card-luxe p-8 text-center text-[#7D636D]">Ainda sem clientes cadastradas.</div>}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {clients.map((c) => (
          <div key={c.phone} className="card-luxe p-5" data-testid={`client-row-${c.phone}`}>
            <div className="font-serif-display text-lg text-[#2A1E22]">{c.name}</div>
            <div className="text-sm text-[#6E555E]">{c.phone}</div>
            <div className="text-xs text-[#7D636D] mt-2">
              {c.bookings_count || 0} agendamento(s){c.last_visit ? ` · última visita em ${c.last_visit.split("-").reverse().join("/")}` : ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
