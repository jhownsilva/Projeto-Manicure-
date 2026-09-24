import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageCircle, Send, Clock3 } from "lucide-react";
import { api, formatApiError } from "@/lib/api";

const STATUS = {
  sent: { label: "Enviado", bg: "#E4F4E5", color: "#2E7D32" },
  mock: { label: "Simulado", bg: "#FAF0D7", color: "#B38059" },
  failed: { label: "Falhou", bg: "#FBE4E4", color: "#B02A2A" },
};
const KIND = { reminder: "Lembrete", booking_created: "Recebimento", confirmed: "Confirmação" };

export function MsgStatus({ status }) {
  const s = STATUS[status] || STATUS.mock;
  return <span className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ backgroundColor: s.bg, color: s.color }} data-testid={`msg-status-${status}`}>{s.label}</span>;
}

export default function RemindersTab() {
  const [data, setData] = useState({ items: [], date: "", mode: "mock" });
  const [log, setLog] = useState([]);
  const [running, setRunning] = useState(false);

  const load = () => {
    api.get("/reminders").then((r) => setData(r.data)).catch((e) => toast.error(formatApiError(e)));
    api.get("/messages").then((r) => setLog(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const run = async () => {
    setRunning(true);
    try {
      const { data: r } = await api.post("/reminders/run");
      toast.success(`Lembretes processados: ${r.total} · enviados ${r.sent} · simulados ${r.mock} · já enviados ${r.skipped}`);
      load();
    } catch (e) { toast.error(formatApiError(e)); }
    finally { setRunning(false); }
  };

  const fmt = (d) => d ? d.split("-").reverse().join("/") : "";

  return (
    <div className="space-y-8">
      <div className="card-luxe p-5 flex flex-col sm:flex-row sm:items-center gap-4" data-testid="reminders-cron-card">
        <Clock3 size={22} className="text-[#C59B27]" />
        <div className="flex-1 text-sm text-[#6E555E]">
          <div className="text-[#2A1E22] font-semibold">Disparo automático todo dia às 9h (Brasília)</div>
          Lembretes dos agendamentos de amanhã ({fmt(data.date)}) são enviados sem você tocar no painel.
          {data.mode === "cloud" ? " WhatsApp Cloud API conectada." : " Em modo simulado: as mensagens ficam registradas aqui com link wa.me."}
        </div>
        <button onClick={run} disabled={running} className="btn-primary inline-flex items-center gap-2 text-sm disabled:opacity-50" data-testid="run-reminders-btn">
          <Send size={14} /> {running ? "Enviando..." : "Disparar agora"}
        </button>
      </div>

      <div>
        <div className="accent-label mb-3">Fila de amanhã</div>
        {(!data.items || data.items.length === 0) ? (
          <div className="card-luxe p-8 text-center text-[#7D636D]" data-testid="reminders-empty">Nenhum lembrete para amanhã.</div>
        ) : (
          <div className="space-y-3" data-testid="reminders-list">
            {data.items.map((r) => (
              <div key={r.id} className="card-luxe p-5" data-testid={`reminder-row-${r.id}`}>
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="font-serif-display text-xl text-[#C59B27] w-20">{r.time}</div>
                  <div className="flex-1">
                    <div className="text-[#2A1E22] font-semibold flex items-center gap-2">{r.client_name} · {r.service_name} {r.reminder_status && <MsgStatus status={r.reminder_status} />}</div>
                    <div className="text-sm text-[#6E555E] mt-1">{r.preview}</div>
                  </div>
                  <a href={r.whatsapp_link} target="_blank" rel="noreferrer noopener" data-testid={`send-reminder-${r.id}`}
                     className="btn-ghost inline-flex items-center gap-2 text-sm">
                    <MessageCircle size={14} /> Abrir no WhatsApp
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="accent-label mb-3">Histórico de mensagens</div>
        {log.length === 0 ? (
          <div className="text-sm text-[#7D636D]" data-testid="messages-empty">Nenhuma mensagem registrada ainda.</div>
        ) : (
          <div className="card-luxe divide-y divide-[#EADCD7]" data-testid="messages-log">
            {log.map((m) => (
              <div key={m.id} className="p-4 flex flex-col sm:flex-row sm:items-center gap-2" data-testid={`message-row-${m.id}`}>
                <div className="text-xs text-[#7D636D] w-36">{new Date(m.created_at).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</div>
                <div className="text-xs font-semibold text-[#B38059] w-28">{KIND[m.kind] || m.kind}</div>
                <div className="flex-1 text-sm text-[#4A353D] truncate">+{m.to} · {m.body}</div>
                <div className="flex items-center gap-2">
                  <MsgStatus status={m.status} />
                  {m.status !== "sent" && <a href={m.wa_link} target="_blank" rel="noreferrer noopener" className="text-[#25D366]" title="Abrir no WhatsApp"><MessageCircle size={16} /></a>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
