'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Send,
  X,
  Sparkles,
  Phone,
  Mail,
  CheckCircle2,
  ExternalLink,
  ShieldCheck,
  Minimize2,
  User,
  Bot,
} from 'lucide-react';

interface Message {
  id: string;
  sender: 'user' | 'admin' | 'system';
  text: string;
  preset?: string | null;
  timestamp: string;
}

const PRESETS = [
  { id: 'tariff', label: '💎 Купить тариф', text: 'Здравствуйте! Хочу узнать информацию по тарифам и подключению.' },
  { id: 'tz', label: '🔍 Подбор поставщиков по ТЗ', text: 'Здравствуйте! Мне нужен подбор производителей/дилеров по техническому заданию.' },
  { id: 'audit', label: '📄 Разбор закупки 44-ФЗ/223-ФЗ', text: 'Здравствуйте! Нужен экспресс-анализ условий закупки и проверка рисков.' },
  { id: 'admin', label: '💬 Связаться с администратором', text: 'Здравствуйте! Хочу проконсультироваться с администратором TenderLex.' },
];

export function ChatWidget() {


  const [isOpen, setIsOpen] = useState(false);
  const [isPillDismissed, setIsPillDismissed] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [contactInput, setContactInput] = useState('');
  const [savedContact, setSavedContact] = useState('');
  const [showContactModal, setShowContactModal] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Open via custom event (e.g. from header 'Чат' button)
  useEffect(() => {
    const handleOpen = () => {
      setIsOpen(true);
      setIsPillDismissed(false);
    };
    window.addEventListener("open_tenderlex_chat", handleOpen);
    (window as unknown as { openTenderlexChat?: () => void }).openTenderlexChat = handleOpen;
    return () => {
      window.removeEventListener("open_tenderlex_chat", handleOpen);
    };
  }, []);

  // 1. Initialize session & storage
  useEffect(() => {
    let sid = localStorage.getItem('tenderlex_chat_session_id');
    if (!sid) {
      sid = 'sess_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 6);
      localStorage.setItem('tenderlex_chat_session_id', sid);
    }
    setSessionId(sid);

    const savedCont = localStorage.getItem('tenderlex_chat_contact') || '';
    setSavedContact(savedCont);

    const savedMsgs = localStorage.getItem('tenderlex_chat_history');
    if (savedMsgs) {
      try {
        setMessages(JSON.parse(savedMsgs));
      } catch {
        initWelcomeMessage();
      }
    } else {
      initWelcomeMessage();
    }
  }, []);

  function initWelcomeMessage() {
    const welcomeMsg: Message = {
      id: 'welcome_1',
      sender: 'admin',
      text: '👋 Здравствуйте! На связи команда TenderLex. Какая задача по закупкам или поиску поставщиков перед вами стоит?',
      timestamp: new Date().toISOString(),
    };
    setMessages([welcomeMsg]);
    try {
      localStorage.setItem('tenderlex_chat_history', JSON.stringify([welcomeMsg]));
    } catch {}
  }

  // 2. Auto-scroll to bottom
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      setUnreadCount(0);
    }
  }, [messages, isOpen]);

  // 3. Polling for admin responses
  useEffect(() => {
    if (!sessionId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/chat/messages?sessionId=${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.messages && Array.isArray(data.messages)) {
            // Check if new admin message arrived
            setMessages((prev) => {
              const currentIds = new Set(prev.map((m) => m.id));
              const currentTexts = new Set(prev.map((m) => `${m.sender}:${(m.text || "").trim()}`));
              const newMsgs = data.messages.filter(
                (m: Message) => !currentIds.has(m.id) && !currentTexts.has(`${m.sender}:${(m.text || "").trim()}`)
              );

              if (newMsgs.length > 0) {
                const updated = [...prev, ...newMsgs];
                try {
                  localStorage.setItem('tenderlex_chat_history', JSON.stringify(updated));
                } catch {}

                if (!isOpen) {
                  setUnreadCount((c) => c + newMsgs.length);
                }
                return updated;
              }
              return prev;
            });
          }
        }
      } catch (e) {
        // Silent poll error
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [sessionId, isOpen]);

  // 4. Send Message Handler
  async function handleSend(textToSend?: string, presetLabel?: string) {
    const msgText = (textToSend || inputText).trim();
    if (!msgText || isSending) return;

    setIsSending(true);

    const userMsg: Message = {
      id: 'user_' + Date.now(),
      sender: 'user',
      text: msgText,
      preset: presetLabel || null,
      timestamp: new Date().toISOString(),
    };

    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInputText('');

    try {
      localStorage.setItem('tenderlex_chat_history', JSON.stringify(newHistory));
    } catch {}

    try {
      await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          text: msgText,
          preset: presetLabel || null,
          contact: savedContact || contactInput || null,
        }),
      });
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setIsSending(false);
    }
  }

  // 5. Save contact handler
  function saveContactInfo() {
    if (contactInput.trim()) {
      setSavedContact(contactInput.trim());
      localStorage.setItem('tenderlex_chat_contact', contactInput.trim());
      setShowContactModal(false);
      // Notify admin about contact update
      handleSend(`[Контакт сохранен]: ${contactInput.trim()}`);
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 font-sans">
      {/* Floating Action Button (Compact Dismissible Pill) */}
      {!isOpen && !isPillDismissed && (
        <div className="relative group flex items-center bg-gradient-to-r from-teal-700 via-teal-800 to-slate-900 text-white pl-2.5 pr-1 py-1 rounded-full shadow-lg hover:shadow-teal-900/30 hover:scale-[1.02] transition-all duration-200 border border-teal-400/30">
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            className="flex items-center gap-1.5 cursor-pointer text-left py-0.5"
            aria-label="Чат с поддержкой TenderLex"
          >
            <div className="relative flex items-center justify-center w-5 h-5 rounded-full bg-white/20 text-white shrink-0">
              <MessageSquare className="w-3 h-3" />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-emerald-400 rounded-full border border-teal-800" />
            </div>

            <span className="font-bold text-[11px] text-white pr-0.5">
              Чат
            </span>

            {unreadCount > 0 && (
              <span className="bg-emerald-400 text-slate-900 text-[9px] font-black px-1.5 py-0.2 rounded-full shadow-xs">
                {unreadCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsPillDismissed(true);
            }}
            className="p-1 text-teal-200/80 hover:text-white hover:bg-white/15 rounded-full transition-colors cursor-pointer ml-0.5"
            title="Скрыть кнопку чата"
            aria-label="Скрыть кнопку чата"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Chat Window Modal */}
      {isOpen && (
        <div className="w-[360px] sm:w-[400px] h-[540px] max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200">
          {/* Header */}
          <div className="bg-gradient-to-r from-slate-900 via-teal-950 to-teal-900 text-white px-4 py-3.5 flex items-center justify-between border-b border-teal-800/40">
            <div className="flex items-center gap-3">
              <div className="relative w-10 h-10 rounded-2xl bg-teal-600/30 border border-teal-400/30 flex items-center justify-center shrink-0 overflow-hidden">
                <img src="/tenderlex-logo.png" alt="TenderLex" className="w-8 h-8 object-contain" />
                <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-400 rounded-full ring-2 ring-slate-900" />
              </div>
              <div className="flex flex-col">
                <h3 className="font-extrabold text-sm text-white flex items-center gap-1.5">
                  Поддержка TenderLex
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                </h3>
                <span className="text-[11px] text-teal-200/90 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
                  Администратор онлайн
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <a
                href="https://t.me/lexelence"
                target="_blank"
                rel="noopener noreferrer"
                title="Написать напрямую в Telegram"
                className="text-teal-200 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Закрыть чат"
                aria-label="Закрыть чат"
                className="text-slate-300 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Presets Bar */}
          <div className="bg-slate-50 border-b border-slate-200/80 p-2.5 flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            {PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSend(p.text, p.label)}
                className="shrink-0 bg-white hover:bg-teal-50 text-slate-700 hover:text-teal-800 border border-slate-200 hover:border-teal-300 font-bold text-[11px] px-2.5 py-1.5 rounded-xl transition-all shadow-2xs"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-slate-50/50">
            {messages.map((m) => {
              const isAdmin = m.sender === 'admin';
              return (
                <div
                  key={m.id}
                  className={`flex flex-col ${isAdmin ? 'items-start' : 'items-end'}`}
                >
                  <div
                    className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                      isAdmin
                        ? 'bg-white text-slate-800 border border-slate-200/90 shadow-2xs rounded-tl-xs'
                        : 'bg-teal-700 text-white shadow-sm rounded-tr-xs'
                    }`}
                  >
                    {m.preset && (
                      <span className="block font-bold text-[10px] uppercase tracking-wider mb-1 text-teal-200 opacity-90">
                        {m.preset}
                      </span>
                    )}
                    <p className="whitespace-pre-wrap">{m.text}</p>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 px-1">
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Contact Banner */}
          {!savedContact ? (
            <div className="bg-amber-50 border-t border-amber-200/80 px-3.5 py-2 flex items-center justify-between text-xs text-amber-900">
              <span className="text-[11px] font-medium">Оставьте контакт для ответа в Telegram / E-mail</span>
              <button
                onClick={() => setShowContactModal(true)}
                className="bg-amber-600 hover:bg-amber-700 text-white font-bold text-[11px] px-2 py-1 rounded-lg transition-colors shadow-2xs"
              >
                Указать
              </button>
            </div>
          ) : (
            <div className="bg-teal-50 border-t border-teal-200/80 px-3.5 py-1.5 flex items-center justify-between text-[11px] text-teal-900">
              <span className="truncate">Контакт: <strong className="font-bold">{savedContact}</strong></span>
              <button
                onClick={() => setShowContactModal(true)}
                className="text-teal-700 underline hover:text-teal-900 text-[10px]"
              >
                изменить
              </button>
            </div>
          )}

          {/* Contact Input Modal Overlay */}
          {showContactModal && (
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-20">
              <div className="bg-white rounded-2xl p-4 w-full max-w-[320px] shadow-2xl border border-slate-200">
                <h4 className="font-extrabold text-sm text-slate-900 mb-1">Оставайтесь на связи</h4>
                <p className="text-xs text-slate-500 mb-3">
                  Укажите ваш телефон, email или логин Telegram, чтобы администратор смог ответить вам при закрытии вкладки.
                </p>
                <input
                  type="text"
                  placeholder="+7 (999) 000-00-00 или @username"
                  value={contactInput}
                  onChange={(e) => setContactInput(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-3 py-2 text-xs mb-3 focus:outline-none focus:border-teal-600"
                />
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => setShowContactModal(false)}
                    className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 font-bold"
                  >
                    Отмена
                  </button>
                  <button
                    onClick={saveContactInfo}
                    className="bg-teal-700 hover:bg-teal-800 text-white font-extrabold text-xs px-3 py-1.5 rounded-xl shadow-xs"
                  >
                    Сохранить
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Footer Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="p-2.5 bg-white border-t border-slate-200 flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Напишите сообщение администратору..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              className="flex-1 bg-slate-100 focus:bg-white text-slate-900 placeholder:text-slate-400 text-xs px-3.5 py-2.5 rounded-xl border border-transparent focus:border-teal-500 focus:outline-none transition-all"
            />
            <button
              type="submit"
              disabled={!inputText.trim() || isSending}
              className="bg-teal-700 hover:bg-teal-800 disabled:opacity-50 text-white p-2.5 rounded-xl transition-all shadow-xs shrink-0"
              aria-label="Отправить сообщение"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}