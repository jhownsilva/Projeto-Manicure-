import { MessageCircle } from "lucide-react";

export default function WhatsAppFab({ phone = "5511999999999", message = "Olá! Gostaria de saber mais sobre os serviços." }) {
  const url = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      data-testid="whatsapp-fab"
      className="fixed bottom-6 left-6 z-40 w-14 h-14 rounded-full bg-[#25D366] hover:bg-[#128C7E] transition-colors duration-200 shadow-lg shadow-[#25D366]/40 flex items-center justify-center"
      aria-label="Falar no WhatsApp"
    >
      <MessageCircle size={26} className="text-white" strokeWidth={2} />
    </a>
  );
}
