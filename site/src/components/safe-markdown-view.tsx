"use client";

import React from "react";
import { ExternalLink } from "lucide-react";

function sanitizeExternalUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

const INLINE_TOKEN_RE =
  /(\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<>)"']+|`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*)/g;

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  if (!text) return [];
  const parts = text.split(INLINE_TOKEN_RE);
  return parts.map((part, idx) => {
    if (!part) return null;
    const key = `${keyPrefix}-${idx}`;
    if (part.startsWith("[") && part.includes("](") && part.endsWith(")")) {
      const splitIdx = part.indexOf("](");
      const label = part.slice(1, splitIdx);
      const rawUrl = part.slice(splitIdx + 2, -1);
      const safeUrl = sanitizeExternalUrl(rawUrl);
      if (safeUrl) {
        return (
          <a
            key={key}
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-teal-700 hover:text-teal-900 underline font-semibold break-words"
          >
            <span>{label}</span>
            <ExternalLink size={12} className="shrink-0 inline" aria-hidden="true" />
          </a>
        );
      }
      return <span key={key}>{label}</span>;
    }
    if (part.startsWith("http://") || part.startsWith("https://")) {
      const cleanedUrl = part.replace(/[.,;:!?)]+$/, "");
      const trailing = part.slice(cleanedUrl.length);
      const safeUrl = sanitizeExternalUrl(cleanedUrl);
      if (safeUrl) {
        let hostLabel = cleanedUrl;
        try {
          const u = new URL(safeUrl);
          hostLabel = u.hostname.replace(/^www\./, "") + (u.pathname !== "/" ? u.pathname.slice(0, 36) : "");
        } catch {
          hostLabel = cleanedUrl.slice(0, 48);
        }
        return (
          <React.Fragment key={key}>
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-teal-700 hover:text-teal-900 underline font-semibold break-all"
            >
              <span>{hostLabel}</span>
              <ExternalLink size={12} className="shrink-0 inline" aria-hidden="true" />
            </a>
            {trailing}
          </React.Fragment>
        );
      }
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={key} className="font-bold text-slate-900">
          {renderInline(part.slice(2, -2), `${key}-b`)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={key} className="px-1.5 py-0.5 bg-slate-100 text-slate-800 rounded text-[12px] font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return (
        <em key={key} className="italic text-slate-700">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim();
  const inner = trimmed.startsWith("|") ? trimmed.slice(1) : trimmed;
  const withoutEnd = inner.endsWith("|") ? inner.slice(0, -1) : inner;
  return withoutEnd.split("|").map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.includes("|") || !trimmed.includes("-")) return false;
  const cells = parseTableRow(trimmed);
  return cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c));
}

export function SafeMarkdownView({ markdown }: { markdown: string }) {
  const lines = (markdown || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push(<hr key={`hr-${i}`} className="my-4 border-slate-200" />);
      i += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,5})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const content = renderInline(headingMatch[2], `h-${i}`);
      if (level <= 2) {
        blocks.push(
          <h3 key={`h-${i}`} className="text-base font-extrabold text-slate-900 mt-5 mb-2">
            {content}
          </h3>
        );
      } else if (level === 3) {
        blocks.push(
          <h4 key={`h-${i}`} className="text-sm font-extrabold text-teal-900 mt-4 mb-2 bg-teal-50/70 px-3 py-1.5 rounded-lg border border-teal-100">
            {content}
          </h4>
        );
      } else {
        blocks.push(
          <h5 key={`h-${i}`} className="text-sm font-bold text-slate-800 mt-3.5 mb-1.5">
            {content}
          </h5>
        );
      }
      i += 1;
      continue;
    }

    if (trimmed.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      const headers = parseTableRow(lines[i]);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|")) {
        if (!isTableSeparator(lines[i])) {
          rows.push(parseTableRow(lines[i]));
        }
        i += 1;
      }
      blocks.push(
        <div key={`tbl-${i}`} className="my-3 overflow-x-auto rounded-xl border border-slate-200 shadow-2xs">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="bg-slate-100 text-slate-800 font-bold border-b border-slate-200">
              <tr>
                {headers.map((h, hIdx) => (
                  <th key={`th-${hIdx}`} className="px-3 py-2 align-top">
                    {renderInline(h, `th-${i}-${hIdx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/80 bg-white">
              {rows.map((r, rIdx) => (
                <tr key={`tr-${rIdx}`} className={rIdx % 2 === 1 ? "bg-slate-50/50" : "bg-white"}>
                  {headers.map((_, cIdx) => {
                    const cellText = r[cIdx] ?? "";
                    const lower = cellText.toLowerCase();
                    const isPositive = lower === "соответствует" || lower.startsWith("соответствует ");
                    const isDeviation = lower.includes("отклонение") || lower.includes("не соответствует");
                    return (
                      <td key={`td-${rIdx}-${cIdx}`} className="px-3 py-2 align-top text-slate-700 leading-relaxed">
                        {isPositive ? (
                          <span className="inline-block px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold text-[11px]">
                            {renderInline(cellText, `td-${i}-${rIdx}-${cIdx}`)}
                          </span>
                        ) : isDeviation ? (
                          <span className="inline-block px-2 py-0.5 rounded-md bg-amber-50 text-amber-900 border border-amber-200 font-semibold text-[11px]">
                            {renderInline(cellText, `td-${i}-${rIdx}-${cIdx}`)}
                          </span>
                        ) : (
                          renderInline(cellText, `td-${i}-${rIdx}-${cIdx}`)
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^(\*|-|•|\d+\.)\s+/.test(trimmed)) {
      const listItems: { indent: number; text: string }[] = [];
      while (i < lines.length) {
        const curRaw = lines[i];
        const curTrim = curRaw.trim();
        const m = curTrim.match(/^(\*|-|•|\d+\.)\s+(.+)$/);
        if (!m) break;
        const leadingSpaces = curRaw.length - curRaw.trimStart().length;
        listItems.push({ indent: leadingSpaces >= 2 ? 1 : 0, text: m[2] });
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${i}`} className="my-2 space-y-1.5 text-[13px] text-slate-700 leading-relaxed">
          {listItems.map((li, lIdx) => (
            <li
              key={`li-${lIdx}`}
              className={`flex items-start gap-2 ${li.indent ? "pl-5 text-slate-600" : ""}`}
            >
              <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
              <span className="flex-1 min-w-0">{renderInline(li.text, `li-${i}-${lIdx}`)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    blocks.push(
      <p key={`p-${i}`} className="my-2 text-[13px] text-slate-700 leading-relaxed">
        {renderInline(trimmed, `p-${i}`)}
      </p>
    );
    i += 1;
  }

  return <div className="space-y-1">{blocks}</div>;
}
