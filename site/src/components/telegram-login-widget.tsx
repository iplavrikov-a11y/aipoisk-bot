"use client";

import { useEffect, useRef } from "react";

interface TelegramLoginWidgetProps {
  botName: string;
  redirectUrl?: string;
  onAuth?: (user: Record<string, unknown>) => void;
  className?: string;
}

export function TelegramLoginWidget({
  botName,
  redirectUrl,
  onAuth,
  className = "",
}: TelegramLoginWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botName.replace(/^@/, ""));
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-request-access", "write");

    if (redirectUrl) {
      const fullUrl = redirectUrl.startsWith("http")
        ? redirectUrl
        : `${typeof window !== "undefined" ? window.location.origin : "https://tenderlex.ru"}${redirectUrl}`;
      script.setAttribute("data-auth-url", fullUrl);
    } else if (onAuth) {
      const callbackName = `onTelegramAuth_${Math.random().toString(36).substring(2, 9)}`;
      (window as unknown as Record<string, unknown>)[callbackName] = onAuth;
      script.setAttribute("data-onauth", `${callbackName}(user)`);
    }

    container.appendChild(script);

    return () => {
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [botName, redirectUrl, onAuth]);

  return (
    <div
      ref={containerRef}
      className={`flex justify-center items-center min-h-[40px] ${className}`}
    />
  );
}
