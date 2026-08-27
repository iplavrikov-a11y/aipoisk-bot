import React, { useMemo, useState, useRef, useEffect } from 'react';
import { FileText, Code, Copy, Check } from 'lucide-react';

interface EmailBodyFrameProps {
  html?: string;
  text?: string;
  className?: string;
  minHeight?: number;
  maxHeight?: number;
  showToggle?: boolean;
}

const escapeHtml = (val: string): string =>
  (val || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const normalizeHref = (href: string): string => {
  const trimmed = href.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (/^mailto:/i.test(trimmed)) return trimmed;
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/i.test(trimmed)) return `mailto:${trimmed}`;
  if (/^www\./i.test(trimmed)) return `https://${trimmed}`;
  return trimmed;
};

const sanitizeHtml = (rawHtml: string): string => {
  return (rawHtml || '')
    .replace(/<base\b[^>]*>/gi, '')
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<meta\b[^>]*http-equiv\s*=\s*(['"]?)refresh\1[^>]*>/gi, '')
    .replace(/<a\b([^>]*?)href=(['"])(.*?)\2([^>]*)>/gi, (_m, before, quote, href, after) => {
      const normalized = normalizeHref(href);
      const attrs = `${before || ''}href=${quote}${normalized}${quote}${after || ''}`;
      const withTarget = /target=/i.test(attrs) ? attrs : `${attrs} target="_blank"`;
      const withRel = /rel=/i.test(withTarget) ? withTarget : `${withTarget} rel="noopener noreferrer"`;
      return `<a${withRel}>`;
    });
};

const renderPlainTextWithLinks = (text: string): string => {
  const escaped = escapeHtml(text || '');
  const pattern = /(https?:\/\/[^\s<]+|www\.[^\s<]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/gi;
  return escaped
    .replace(pattern, (match) => {
      const href = normalizeHref(match);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;text-decoration:underline;">${match}</a>`;
    })
    .replace(/\n/g, '<br/>');
};

const buildEmailSrcDoc = (bodyHtml?: string, bodyText?: string): string => {
  const content = bodyHtml ? sanitizeHtml(bodyHtml) : renderPlainTextWithLinks(bodyText || '(Текст сообщения отсутствует)');

  return `<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      html, body {
        margin: 0;
        padding: 0;
        background: #ffffff;
        color: #1e293b;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 13.5px;
        line-height: 1.6;
      }
      body {
        padding: 12px 14px;
        user-select: text;
        -webkit-user-select: text;
        word-break: break-word;
        overflow-wrap: anywhere;
      }
      a {
        color: #2563eb;
        text-decoration: underline;
        text-underline-offset: 2px;
        cursor: pointer;
      }
      a:hover {
        color: #1d4ed8;
      }
      table {
        border-collapse: collapse;
        width: 100% !important;
        max-width: 100% !important;
        margin: 10px 0;
        table-layout: auto !important;
        font-size: 13px;
      }
      col, colgroup {
        width: auto !important;
        max-width: 100% !important;
      }
      td, th {
        border: 1px solid #e2e8f0;
        padding: 6px 10px;
        white-space: normal !important;
        word-break: break-word;
        box-sizing: border-box;
        max-width: 100% !important;
      }
      th {
        background: #f8fafc;
        font-weight: 600;
      }
      img {
        max-width: 100%;
        height: auto;
      }
      p {
        margin: 0 0 10px 0;
      }
      p:last-child {
        margin-bottom: 0;
      }
      blockquote {
        margin: 8px 0;
        padding: 4px 12px;
        border-left: 3px solid #cbd5e1;
        color: #64748b;
      }
      pre, code {
        white-space: pre-wrap;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 12.5px;
        background: #f1f5f9;
        border-radius: 4px;
        padding: 2px 4px;
      }
      hr {
        border: 0;
        border-top: 1px solid #e2e8f0;
        margin: 14px 0;
      }
    </style>
  </head>
  <body>${content}</body>
</html>`;
};

const EmailBodyFrameComponent: React.FC<EmailBodyFrameProps> = ({
  html,
  text,
  className = '',
  minHeight = 120,
  maxHeight = 1600,
  showToggle = true,
}) => {
  const hasHtml = Boolean(html && html.trim().length > 0);
  const [viewMode, setViewMode] = useState<'html' | 'text'>(hasHtml ? 'html' : 'text');
  const [height, setHeight] = useState<number>(minHeight);
  const [copied, setCopied] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Sync mode if html becomes available
  useEffect(() => {
    if (hasHtml && viewMode === 'text' && !text) {
      setViewMode('html');
    }
  }, [hasHtml, text]);

  const srcDoc = useMemo(() => {
    if (viewMode === 'html' && hasHtml) {
      return buildEmailSrcDoc(html, text);
    }
    return buildEmailSrcDoc(undefined, text || '(Текст сообщения отсутствует)');
  }, [viewMode, hasHtml, html, text]);

  const handleCopy = () => {
    const contentToCopy = text || (html ? html.replace(/<[^>]+>/g, '') : '');
    navigator.clipboard.writeText(contentToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const adjustIframeHeight = (iframe: HTMLIFrameElement | null) => {
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument;
      if (!doc || !doc.body) return;
      const scrollH = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
      const nextHeight = Math.max(minHeight, Math.min(maxHeight, scrollH + 16));
      setHeight(nextHeight);

      // Forward mousedown to document for outside click handlers
      doc.addEventListener('mousedown', (ev) => {
        window.dispatchEvent(
          new MouseEvent('mousedown', {
            bubbles: true,
            cancelable: true,
            clientX: ev.clientX,
            clientY: ev.clientY,
          })
        );
      });
    } catch {
      setHeight(minHeight);
    }
  };

  return (
    <div className={`email-body-container ${className}`} style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      {/* View Toggle Bar (if HTML is available) */}
      {showToggle && (hasHtml || text) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '4px 8px',
            marginBottom: 6,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            fontSize: 11.5,
          }}
        >
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {hasHtml && (
              <>
                <button
                  type="button"
                  onClick={() => setViewMode('html')}
                  className="outreach-btn"
                  style={{
                    padding: '2px 8px',
                    fontSize: 11,
                    fontWeight: viewMode === 'html' ? 700 : 400,
                    background: viewMode === 'html' ? '#ffffff' : 'transparent',
                    color: viewMode === 'html' ? '#0f172a' : '#64748b',
                    borderColor: viewMode === 'html' ? '#cbd5e1' : 'transparent',
                    boxShadow: viewMode === 'html' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <Code size={11} />
                  <span>Форматированный вид (HTML)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('text')}
                  className="outreach-btn"
                  style={{
                    padding: '2px 8px',
                    fontSize: 11,
                    fontWeight: viewMode === 'text' ? 700 : 400,
                    background: viewMode === 'text' ? '#ffffff' : 'transparent',
                    color: viewMode === 'text' ? '#0f172a' : '#64748b',
                    borderColor: viewMode === 'text' ? '#cbd5e1' : 'transparent',
                    boxShadow: viewMode === 'text' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <FileText size={11} />
                  <span>Простой текст</span>
                </button>
              </>
            )}
            {!hasHtml && (
              <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                <FileText size={11} />
                <span>Текстовый ответ</span>
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="outreach-btn outreach-btn-ghost"
            style={{ padding: '2px 8px', fontSize: 11, color: copied ? '#10b981' : '#64748b' }}
            title="Скопировать текст письма"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Скопировано' : 'Копировать'}</span>
          </button>
        </div>
      )}

      {/* Frame Rendering */}
      <iframe
        ref={iframeRef}
        title="Email Body"
        srcDoc={srcDoc}
        sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
        style={{
          width: '100%',
          height: `${height}px`,
          minHeight: `${minHeight}px`,
          maxHeight: `${maxHeight}px`,
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          background: '#ffffff',
          boxSizing: 'border-box',
          display: 'block',
        }}
        onLoad={(e) => adjustIframeHeight(e.currentTarget)}
      />
    </div>
  );
};

export const EmailBodyFrame = React.memo(EmailBodyFrameComponent, (prev, next) => {
  return (
    prev.html === next.html &&
    prev.text === next.text &&
    prev.className === next.className &&
    prev.minHeight === next.minHeight &&
    prev.maxHeight === next.maxHeight &&
    prev.showToggle === next.showToggle
  );
});

export default EmailBodyFrame;
