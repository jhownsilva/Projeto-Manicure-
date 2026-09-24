import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Check, Clock, Sparkles, MessageCircle } from "lucide-react";
import Navbar from "@/components/Navbar";
import { api, formatApiError } from "@/lib/api";

function useQueryParam(name) {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search).get(name), [search, name]);
}

function formatDateBR(d) {
  return d.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "short" });
}
function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function Booking() {
  const preset = useQueryParam("service");
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [services, setServices] = useState([]);
  const [service, setService] = useState(null);
  const [dates, setDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [selectedTime, setSelectedTime] = useState(null);
  const [form, setForm] = useState({ name: "", phone: "", email: "", notes: "" });
  const [confirming, setConfirming] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [salon, setSalon] = useState({ name: "Studio Gel & Beauty", whatsapp: "5511999999999" });

  useEffect(() => {
    api.get("/services").then((r) => {
      setServices(r.data);
      if (preset) {
        const found = r.data.find((s) => s.id === preset);
        if (found) { setService(found); setStep(2); }
      }
    }).catch(() => {});
    api.get("/salon").then((r) => setSalon(r.data)).catch(() => {});

    const arr = [];
    const today = new Date();
    for (let i = 0; i < 14; i++) {
      const d = new Date(today); d.setDate(today.getDate() + i);
      arr.push(d);
    }
    setDates(arr);
  }, [preset]);

  useEffect(() => {
    if (!service || !selectedDate) return;
    setSlots([]); setSelectedTime(null);
    api.get(`/services/${service.id}/slots`, { params: { date: ymd(selectedDate) } })
      .then((r) => setSlots(r.data.slots || []))
      .catch((e) => toast.error(formatApiError(e)));
  }, [service, selectedDate]);

  const chooseService = (s) => { setService(s); setStep(2); };
  const goStep = (n) => setStep(n);

  const confirmBooking = async () => {
    if (!service || !selectedDate || !selectedTime) return;
    if (!form.name.trim() || !form.phone.trim()) {
      toast.error("Informe nome e telefone para confirmar.");
      return;
    }
    setConfirming(true);
    try {
      const { data } = await api.post("/bookings", {
        service_id: service.id,
        date: ymd(selectedDate),
        time: selectedTime,
        client_name: form.name,
        client_phone: form.phone,
        client_email: form.email,
        notes: form.notes,
      });
      setConfirmation(data);
      toast.success("Agendamento criado! Confirme no WhatsApp.");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar salonName={salon.name} />
      <div className="max-w-3xl mx-auto px-5 sm:px-8 py-10">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8" data-testid="booking-stepper">
          {[1, 2, 3].map((n) => (
            <div key={n} className="flex-1">
              <div className={`h-1.5 rounded-full ${step >= n ? "bg-gradient-to-r from-[#D47385] to-[#C59B27]" : "bg-[#EADCD7]"}`} />
              <div className={`mt-2 text-xs uppercase tracking-wider font-semibold ${step >= n ? "text-[#B38059]" : "text-[#B9A3A9]"}`}>
                Passo {n}
              </div>
            </div>
          ))}
        </div>

        {confirmation ? (
          <ConfirmationView data={confirmation} onNew={() => { setConfirmation(null); setStep(1); setService(null); setSelectedDate(null); setSelectedTime(null); setForm({ name:"", phone:"", email:"", notes:"" }); }} />
        ) : step === 1 ? (
          <div>
            <h1 className="font-serif-display text-3xl sm:text-4xl text-[#2A1E22] mb-2">Escolha o serviço</h1>
            <p className="text-[#6E555E] mb-8">Toque no serviço desejado para continuar.</p>
            <div className="grid sm:grid-cols-2 gap-4" data-testid="booking-services">
              {services.map((s) => (
                <button key={s.id} onClick={() => chooseService(s)}
                  className="card-luxe p-5 text-left hover:-translate-y-0.5 transition-transform duration-200"
                  data-testid={`pick-service-${s.id}`}>
                  <div className="flex items-center gap-4">
                    {s.image_url && <img src={s.image_url} alt="" className="w-16 h-16 rounded-xl object-cover" />}
                    <div className="flex-1">
                      <div className="font-serif-display text-lg text-[#2A1E22]">{s.name}</div>
                      <div className="text-sm text-[#6E555E] flex items-center gap-3 mt-1">
                        <span className="flex items-center gap-1"><Clock size={13} /> {s.duration_min} min</span>
                        <span className="text-[#C59B27] font-semibold">R$ {s.price.toFixed(2).replace(".", ",")}</span>
                      </div>
                    </div>
                    <ArrowRight size={18} className="text-[#B38059]" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : step === 2 ? (
          <div>
            <button onClick={() => goStep(1)} className="text-sm text-[#B38059] mb-4 flex items-center gap-1" data-testid="back-to-service"><ArrowLeft size={14} /> Trocar serviço</button>
            <h1 className="font-serif-display text-3xl sm:text-4xl text-[#2A1E22] mb-1">Data & horário</h1>
            <p className="text-[#6E555E] mb-6">{service?.name} · {service?.duration_min} min · R$ {service?.price.toFixed(2).replace(".", ",")}</p>

            <div className="mb-4 accent-label">Escolha o dia</div>
            <div className="flex gap-2 overflow-x-auto pb-3 -mx-1 px-1" data-testid="date-strip">
              {dates.map((d) => {
                const active = selectedDate && ymd(selectedDate) === ymd(d);
                return (
                  <button key={ymd(d)} onClick={() => setSelectedDate(d)}
                    data-testid={`date-btn-${ymd(d)}`}
                    className={`flex-shrink-0 w-20 py-3 rounded-xl border transition-colors duration-200 ${active ? "bg-[#D47385] text-white border-[#D47385]" : "bg-white border-[#EADCD7] text-[#4A353D] hover:border-[#D47385]"}`}>
                    <div className="text-[10px] uppercase tracking-wider">{formatDateBR(d).split(",")[0]}</div>
                    <div className="text-xl font-serif-display">{d.getDate()}</div>
                    <div className="text-[10px]">{d.toLocaleDateString("pt-BR", { month: "short" })}</div>
                  </button>
                );
              })}
            </div>

            <div className="mt-8 mb-3 accent-label">Horários disponíveis</div>
            {selectedDate ? (
              slots.length ? (
                <div className="grid grid-cols-4 sm:grid-cols-6 gap-2" data-testid="slot-grid">
                  {slots.map((slot) => (
                    <button key={slot.time} disabled={!slot.available}
                      onClick={() => setSelectedTime(slot.time)}
                      data-testid={`slot-${slot.time}`}
                      className={`slot-btn ${selectedTime === slot.time ? "selected" : ""}`}>
                      {slot.time}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-[#7D636D]">Carregando horários...</div>
              )
            ) : (
              <div className="text-sm text-[#7D636D]">Selecione uma data acima.</div>
            )}

            <div className="mt-10 flex justify-end">
              <button disabled={!selectedTime} onClick={() => goStep(3)} className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-2" data-testid="continue-to-details">
                Continuar <ArrowRight size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div>
            <button onClick={() => goStep(2)} className="text-sm text-[#B38059] mb-4 flex items-center gap-1" data-testid="back-to-datetime"><ArrowLeft size={14} /> Voltar</button>
            <h1 className="font-serif-display text-3xl sm:text-4xl text-[#2A1E22] mb-1">Seus dados</h1>
            <p className="text-[#6E555E] mb-6">Confirmação enviada por WhatsApp em seguida.</p>

            <div className="card-luxe p-6 mb-6 flex items-start gap-4">
              <Sparkles size={22} className="text-[#C59B27] mt-1" />
              <div>
                <div className="font-serif-display text-lg text-[#2A1E22]">{service?.name}</div>
                <div className="text-sm text-[#6E555E]">
                  {selectedDate && formatDateBR(selectedDate)} · {selectedTime} · R$ {service?.price.toFixed(2).replace(".", ",")}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <Field label="Nome completo" required value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="input-name" />
              <Field label="WhatsApp (com DDD)" required value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testId="input-phone" placeholder="(11) 99999-9999" />
              <Field label="E-mail (opcional)" value={form.email} onChange={(v) => setForm({ ...form, email: v })} testId="input-email" />
              <div>
                <label className="block text-sm font-medium text-[#4A353D] mb-1.5">Observações</label>
                <textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  data-testid="input-notes"
                  className="w-full rounded-xl border border-[#EADCD7] bg-white px-4 py-3 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200" />
              </div>
            </div>

            <button onClick={confirmBooking} disabled={confirming} className="btn-primary w-full mt-8 inline-flex items-center justify-center gap-2 disabled:opacity-50" data-testid="confirm-booking-btn">
              {confirming ? "Enviando..." : (<><Check size={18} /> Confirmar agendamento</>)}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, required, testId, placeholder, type="text" }) {
  return (
    <div>
      <label className="block text-sm font-medium text-[#4A353D] mb-1.5">
        {label} {required && <span className="text-[#D47385]">*</span>}
      </label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        data-testid={testId}
        className="w-full rounded-xl border border-[#EADCD7] bg-white px-4 py-3 text-[#2A1E22] focus:border-[#D47385] focus:outline-none transition-colors duration-200" />
    </div>
  );
}

function ConfirmationView({ data, onNew }) {
  const b = data.booking;
  return (
    <div className="card-luxe p-8 text-center" data-testid="booking-confirmation">
      <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#D47385] to-[#C59B27] mx-auto flex items-center justify-center mb-4">
        <Check size={30} className="text-white" strokeWidth={3} />
      </div>
      <h2 className="font-serif-display text-3xl text-[#2A1E22] mb-2">Agendamento criado!</h2>
      <p className="text-[#6E555E] mb-6">
        {b.service_name} em {b.date.split("-").reverse().join("/")} às {b.time} para <strong>{b.client_name}</strong>.
      </p>
      <div className="chip mx-auto mb-6">Status: aguardando confirmação</div>
      <a href={data.whatsapp_link} target="_blank" rel="noreferrer noopener"
         className="btn-primary w-full inline-flex items-center justify-center gap-2 mb-3"
         data-testid="whatsapp-confirm-btn">
        <MessageCircle size={18} /> Confirmar no WhatsApp
      </a>
      <button onClick={onNew} className="btn-ghost w-full" data-testid="new-booking-btn">Agendar outro horário</button>
      <div className="mt-6">
        <Link to="/" className="text-sm text-[#B38059] hover:underline" data-testid="back-home-link">Voltar para o início</Link>
      </div>
    </div>
  );
}
