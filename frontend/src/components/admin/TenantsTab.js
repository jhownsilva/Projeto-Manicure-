import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, ExternalLink, Building2 } from "lucide-react";
import { api, formatApiError } from "@/lib/api";

const empty = { slug: "", name: "", category: "Beleza", whatsapp: "", owner_name: "", owner_email: "", owner_password: "" };

export default function TenantsTab({ onChanged }) {
  const [tenants, setTenants] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = () => api.get("/admin/tenants").then((r) => setTenants(r.data)).catch((e) => toast.error(formatApiError(e)));
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/admin/tenants", form);
      toast.success("Salão criado! A dona já pode fazer login.");
      setOpen(false); setForm(empty); load(); onChanged?.();
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setSaving(false); }
  };
  const remove = async (t) => {
    if (!window.confirm(`Remover "${t.name}" e todos os seus dados?`)) return;
    try { await api.delete(`/admin/tenants/${t.id}`); toast.success("Salão removido"); load(); onChanged?.(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const input = "w-full rounded-xl border border-[#EADCD7] bg-white px-3 py-2 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200";
  const label = "block text-xs uppercase tracking-wider text-[#7D636D] font-semibold mb-1";
  const F = ({ k, l, type = "text", ph }) => (
    <div><label className={label}>{l}</label><input type={type} placeholder={ph} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`tenant-${k}`} className={input} /></div>
  );

  return (
    <div data-testid="tenants-tab">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <p className="text-sm text-[#6E555E]">Cada salão tem sua própria vitrine, agenda, serviços e dona. Use o seletor no topo para administrar qualquer um deles.</p>
        <button onClick={() => setOpen(true)} className="btn-primary inline-flex items-center gap-2" data-testid="new-tenant-btn"><Plus size={14} /> Novo salão</button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tenants.map((t) => (
          <div key={t.id} className="card-luxe p-5" data-testid={`tenant-card-${t.slug}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-serif-display text-lg text-[#2A1E22] flex items-center gap-2"><Building2 size={16} className="text-[#B38059]" /> {t.name}</div>
                <div className="text-xs text-[#7D636D]">{t.category} · /s/{t.slug}</div>
              </div>
              <button onClick={() => remove(t)} data-testid={`delete-tenant-${t.slug}`} className="p-2 rounded-full hover:bg-[#FBE4E4] text-[#B02A2A]"><Trash2 size={15} /></button>
            </div>
            <div className="text-sm text-[#6E555E] mt-3">{t.services_count} serviço(s) · {t.bookings_count} agendamento(s)</div>
            {t.owner && <div className="text-xs text-[#7D636D] mt-1">Dona: {t.owner.name} · {t.owner.email}</div>}
            <a href={`/s/${t.slug}`} target="_blank" rel="noreferrer" className="text-sm text-[#B38059] hover:underline inline-flex items-center gap-1 mt-3" data-testid={`open-tenant-${t.slug}`}>
              Abrir vitrine <ExternalLink size={12} />
            </a>
          </div>
        ))}
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-3" onClick={(e) => e.stopPropagation()} data-testid="tenant-modal">
            <h3 className="font-serif-display text-2xl text-[#2A1E22]">Novo salão</h3>
            <div className="grid grid-cols-2 gap-3">
              <F k="name" l="Nome" ph="Clínica Sorriso" />
              <F k="slug" l="Slug (URL)" ph="clinica-sorriso" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <F k="category" l="Categoria" ph="Dentista" />
              <F k="whatsapp" l="WhatsApp" ph="5511999999999" />
            </div>
            <div className="gold-divider" />
            <div className="text-xs uppercase tracking-wider text-[#B38059] font-semibold">Acesso da dona</div>
            <F k="owner_name" l="Nome" />
            <F k="owner_email" l="E-mail" type="email" />
            <F k="owner_password" l="Senha (mín. 6)" type="password" />
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setOpen(false)} className="btn-ghost" data-testid="tenant-cancel">Cancelar</button>
              <button onClick={create} disabled={saving} className="btn-primary disabled:opacity-50" data-testid="tenant-save">{saving ? "Criando..." : "Criar salão"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
