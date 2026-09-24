import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Check, Loader2, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [data, setData] = useState(null);
  const [state, setState] = useState("polling"); // polling | paid | expired | timeout | error

  useEffect(() => {
    if (!sessionId) { setState("error"); return; }
    let attempts = 0; let timer;
    const poll = async () => {
      try {
        const { data: d } = await api.get(`/payments/status/${sessionId}`);
        setData(d);
        if (d.payment_status === "paid") { setState("paid"); return; }
        if (["expired", "failed"].includes(d.payment_status)) { setState("expired"); return; }
      } catch { setState("error"); return; }
      if (++attempts >= 8) { setState("timeout"); return; }
      timer = setTimeout(poll, 2000);
    };
    poll();
    return () => clearTimeout(timer);
  }, [sessionId]);

  const b = data?.booking;
  const home = data?.tenant_slug ? `/s/${data.tenant_slug}` : "/";
  const money = (v) => `R$ ${Number(v || 0).toFixed(2).replace(".", ",")}`;

  return (
    <div className="min-h-screen flex items-center justify-center px-5 py-10 bg-gradient-to-br from-[#FDF9F8] via-[#F8EFEA] to-[#FAF0D7]/40">
      <div className="card-luxe p-8 max-w-md w-full text-center" data-testid="payment-result">
        {state === "polling" && (
          <>
            <Loader2 size={40} className="mx-auto text-[#D47385] animate-spin mb-4" />
            <h1 className="font-serif-display text-2xl text-[#2A1E22]">Confirmando pagamento...</h1>
            <p className="text-sm text-[#6E555E] mt-2">Aguarde alguns segundos.</p>
          </>
        )}
        {state === "paid" && (
          <>
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#D47385] to-[#C59B27] mx-auto flex items-center justify-center mb-4">
              <Check size={30} className="text-white" strokeWidth={3} />
            </div>
            <h1 className="font-serif-display text-3xl text-[#2A1E22] mb-2" data-testid="payment-paid-title">Sinal pago!</h1>
            <p className="text-[#6E555E]">
              Seu horário de <strong>{b?.service_name}</strong> em {b?.date?.split("-").reverse().join("/")} às {b?.time} está confirmado no {data?.tenant_name}.
            </p>
            <div className="chip mx-auto mt-4" data-testid="deposit-amount-chip">Sinal: {money(data?.amount)}</div>
          </>
        )}
        {(state === "expired" || state === "error") && (
          <>
            <AlertTriangle size={40} className="mx-auto text-[#B02A2A] mb-4" />
            <h1 className="font-serif-display text-2xl text-[#2A1E22]">Pagamento não concluído</h1>
            <p className="text-sm text-[#6E555E] mt-2">Seu agendamento continua aguardando confirmação. Você pode tentar novamente ou confirmar pelo WhatsApp.</p>
          </>
        )}
        {state === "timeout" && (
          <>
            <AlertTriangle size={40} className="mx-auto text-[#B38059] mb-4" />
            <h1 className="font-serif-display text-2xl text-[#2A1E22]">Ainda processando</h1>
            <p className="text-sm text-[#6E555E] mt-2">O pagamento está sendo confirmado. Você receberá a confirmação em breve.</p>
          </>
        )}
        <Link to={home} className="btn-primary w-full inline-flex justify-center mt-8" data-testid="payment-back-home">Voltar para o início</Link>
      </div>
    </div>
  );
}
