import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

export default function PWAInstall() {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem("pwa_dismissed");
    if (dismissed) return;
    const handler = (e) => {
      e.preventDefault();
      setDeferred(e);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    await deferred.userChoice;
    setVisible(false);
    setDeferred(null);
  };

  const dismiss = () => {
    localStorage.setItem("pwa_dismissed", "1");
    setVisible(false);
  };

  if (!visible) return null;
  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-white border border-[#E2C889]/60 shadow-[0_0_25px_rgba(197,155,39,0.2)] rounded-full px-5 py-3 flex items-center gap-3"
      data-testid="pwa-install-banner"
    >
      <Download size={18} className="text-[#C59B27]" />
      <span className="text-sm text-[#2A1E22]">Instalar app do salão</span>
      <button onClick={install} className="btn-primary py-1.5 px-4 text-sm" data-testid="pwa-install-btn">Instalar</button>
      <button onClick={dismiss} className="p-1 text-[#7D636D]" data-testid="pwa-install-dismiss" aria-label="Dispensar">
        <X size={16} />
      </button>
    </div>
  );
}
