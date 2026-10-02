'use client';

import { MessageSquare } from "lucide-react";

export function ContactChatButton() {
  return (
    <button
      type="button"
      onClick={() => {
        window.dispatchEvent(new CustomEvent("open_tenderlex_chat"));
        (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat?.();
      }}
      className="py-3 px-5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-teal-500 hover:shadow-md transition-all group flex items-center justify-center gap-2 shrink-0 min-w-[140px] cursor-pointer"
    >
      <MessageSquare size={16} className="text-teal-600 shrink-0" />
      <strong className="text-sm font-bold text-slate-900 group-hover:text-teal-700">
        Чат на сайте
      </strong>
    </button>
  );
}
