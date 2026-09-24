import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, MessageCircle, CreditCard } from "lucide-react";
import { api, formatApiError } from "@/lib/api";

const FIELDS = [
  ["name", "Nome do salão"], ["category", "Categoria (ex.: Manicure, Barbearia, Dentista)"], ["tagline", "Frase de destaque (eyebrow)"],
  ["hero_title", "Título principal"], ["hero_subtitle", "Subtítulo"], ["hero_image", "URL da imagem principal"],
  ["address", "Endereço"], ["phone_display", "Telefone exibido"], ["instagram", "Instagram"],
  ["whatsapp", "WhatsApp do salão (somente números, com 55)"], ["testimonial", "Depoimento"], ["testimonial_author", "Autora do depoimento"],
];

export default function SettingsTab({ onSaved }) {
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [wa, setWa] = useState({ mode: "mock" });

  useEffect(() => {
    api.get("/settings").then((r) => setForm({ ...r.data, gallery_text: (r.data.gallery || []).join("\n") })).catch((e) => toast.error(formatApiError(e)));
    api.get("/whatsapp/status").then((r) => setWa(r.data)).catch(() => {});
  }, []);

  if (!form) return <div className="text-[#7D636D]">Carregando...</div>;
  const set = (k, v) => setForm({ ...form, [k]: v });

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        ...FIELDS.reduce((acc, [k]) => ({ ...acc, [k]: form[k] ?? "" }), {}),
        gallery: form.gallery_text.split("\n").map((s) => s.trim()).filter(Boolean),
        open_hour: Number(form.open_hour), close_hour: Number(form.close_hour), slot_minutes: Number(form.slot_minutes),
        deposit_enabled: !!form.deposit_enabled, deposit_percent: Number(form.deposit_percent),
      };
      const { data } = await api.put("/settings", payload);
      setForm({ ...data, gallery_text: (data.gallery || []).join("\n") });
      toast.success("Configurações salvas");
      onSaved?.();
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setSaving(false); }
  };

  const input = "w-full rounded-xl border border-[#EADCD7] bg-white px-3 py-2 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200";
  const label = "block text-xs uppercase tracking-wider text-[#7D636D] font-semibold mb-1";

  return (
    <div className="grid lg:grid-cols-3 gap-6" data-testid="settings-tab">
      <div className="lg:col-span-2 card-luxe p-6 space-y-3">
        <h3 className="font-serif-display text-xl text-[#2A1E22]">Dados do salão & vitrine</h3>
        <div className="text-xs text-[#7D636D]">Link público: <code className="bg-[#F8EFEA] px-1.5 py-0.5 rounded" data-testid="public-link">/s/{form.slug}</code></div>
        {FIELDS.map(([k, l]) => (
          <div key={k}>
            <label className={label}>{l}</label>
            {k === "hero_subtitle" || k === "testimonial" ? (
              <textarea rows={2} value={form[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`setting-${k}`} className={input} />
            ) : (
              <input value={form[k] || ""} onChange={(e) => set(k, e.target.value)} data-testid={`setting-${k}`} className={input} />
            )}
          </div>
        ))}
        <div>
          <label className={label}>Galeria (uma URL por linha)</label>
          <textarea rows={4} value={form.gallery_text} onChange={(e) => set("gallery_text", e.target.value)} data-testid="setting-gallery" className={input} />
        </div>
      </div>

      <div className="space-y-6">
        <div className="card-luxe p-6 space-y-3">
          <h3 className="font-serif-display text-xl text-[#2A1E22]">Horário de funcionamento</h3>
          <div className="grid grid-cols-3 gap-3">
            <div><label className={label}>Abre (h)</label><input type="number" min={0} max={23} value={form.open_hour} onChange={(e) => set("open_hour", e.target.value)} data-testid="setting-open_hour" className={input} /></div>
            <div><label className={label}>Fecha (h)</label><input type="number" min={1} max={24} value={form.close_hour} onChange={(e) => set("close_hour", e.target.value)} data-testid="setting-close_hour" className={input} /></div>
            <div><label className={label}>Slot (min)</label><input type="number" min={10} step={5} value={form.slot_minutes} onChange={(e) => set("slot_minutes", e.target.value)} data-testid="setting-slot_minutes" className={input} /></div>
          </div>
        </div>

        <div className="card-luxe p-6 space-y-3">
          <h3 className="font-serif-display text-xl text-[#2A1E22] flex items-center gap-2"><CreditCard size={18} className="text-[#C59B27]" /> Sinal no agendamento</h3>
          <label className="flex items-center gap-2 text-sm text-[#4A353D]">
            <input type="checkbox" checked={!!form.deposit_enabled} onChange={(e) => set("deposit_enabled", e.target.checked)} data-testid="setting-deposit_enabled" />
            Oferecer sinal opcional via Stripe
          </label>
          <div>
            <label className={label}>Percentual do serviço (%)</label>
            <input type="number" min={1} max={100} value={form.deposit_percent} onChange={(e) => set("deposit_percent", e.target.value)} data-testid="setting-deposit_percent" className={input} />
          </div>
          <p className="text-xs text-[#7D636D]">Ao pagar o sinal, o agendamento é confirmado automaticamente e a cliente recebe a confirmação por WhatsApp.</p>
        </div>

        <div className="card-luxe p-6 space-y-2" data-testid="whatsapp-status-card">
          <h3 className="font-serif-display text-xl text-[#2A1E22] flex items-center gap-2"><MessageCircle size={18} className="text-[#25D366]" /> WhatsApp</h3>
          {wa.mode === "cloud" ? (
            <div className="text-sm text-[#2E7D32] font-medium" data-testid="wa-mode-cloud">Meta Cloud API conectada · envios automáticos ativos</div>
          ) : (
            <div className="text-sm text-[#B38059]" data-testid="wa-mode-mock">
              Modo simulado: mensagens são registradas e abertas via link wa.me. Para ativar envios automáticos, configure
              <code className="mx-1 bg-[#F8EFEA] px-1 rounded">WHATSAPP_ACCESS_TOKEN</code> e
              <code className="mx-1 bg-[#F8EFEA] px-1 rounded">WHATSAPP_PHONE_NUMBER_ID</code> no servidor.
            </div>
          )}
        </div>

        <button onClick={save} disabled={saving} className="btn-primary w-full inline-flex items-center justify-center gap-2 disabled:opacity-50" data-testid="settings-save-btn">
          <Save size={16} /> {saving ? "Salvando..." : "Salvar configurações"}
        </button>
      </div>
    </div>
  );
}
