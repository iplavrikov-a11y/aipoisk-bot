"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, Info } from "lucide-react";

function TableScrollBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-full max-w-full min-w-0 overflow-x-auto rounded-xl border border-slate-200 shadow-2xs bg-white [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-track]:bg-slate-100 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-400/75 hover:[&::-webkit-scrollbar-thumb]:bg-slate-500">
      {children}
    </div>
  );
}

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
            className="inline text-teal-700 hover:text-teal-900 underline font-semibold [overflow-wrap:anywhere]"
          >
            <span>{label}</span>
            <ExternalLink size={11} className="inline ml-1 -mt-0.5 shrink-0" aria-hidden="true" />
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

function extractKeyValue(text: string): { label: string; value: string } | null {
  const mBold = text.match(/^\*\*([^*:\n]{2,65}?):\*\*\s*(.+)$/);
  if (mBold) {
    return { label: mBold[1].trim(), value: mBold[2].trim() };
  }
  const mBoldInside = text.match(/^\*\*([^*:\n]{2,65}?)\*\*\s*:\s*(.+)$/);
  if (mBoldInside) {
    return { label: mBoldInside[1].trim(), value: mBoldInside[2].trim() };
  }
  return null;
}

type ListNode = {
  ordered: boolean;
  numLabel: string;
  text: string;
  children: { indent: number; ordered: boolean; numLabel: string; text: string }[];
};

function renderCalloutParagraph(text: string, key: string): React.ReactNode | null {
  const plainStart = text.replace(/^[*_`]+/, "");
  const isVerdict = /^(ИТОГОВЫЙ ВЕРДИКТ|ВЕРДИКТ|ИТОГ|РЕКОМЕНДАЦИЯ|ВЫВОД)\s*:/i.test(plainStart);
  const isWarning = /^(ВАЖНО|ВНИМАНИЕ|КРИТИЧН[ОЫ]|РИСК|ОСТОРОЖНО)\s*:/i.test(plainStart);
  const isLegal = /^(ПРАВОВОЙ ВЫВОД|ЦИТАТА)\s*:/i.test(plainStart);

  if (isVerdict) {
    return (
      <div
        key={key}
        className="rounded-xl border border-emerald-200 bg-emerald-50/70 px-3.5 py-2.5 text-[13px] text-slate-900 leading-relaxed flex items-start gap-2.5"
      >
        <CheckCircle2 size={16} className="text-emerald-700 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">{renderInline(text, key)}</div>
      </div>
    );
  }
  if (isWarning) {
    return (
      <div
        key={key}
        className="rounded-xl border border-amber-200 bg-amber-50/75 px-3.5 py-2.5 text-[13px] text-amber-950 leading-relaxed flex items-start gap-2.5"
      >
        <AlertTriangle size={16} className="text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">{renderInline(text, key)}</div>
      </div>
    );
  }
  if (isLegal) {
    return (
      <div
        key={key}
        className="rounded-xl border-l-4 border-teal-500 bg-teal-50/50 px-3.5 py-2 text-[13px] text-slate-800 leading-relaxed flex items-start gap-2"
      >
        <Info size={15} className="text-teal-700 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="min-w-0 flex-1">{renderInline(text, key)}</div>
      </div>
    );
  }
  return null;
}

function StatusPill({
  label,
  dotColor,
  bgColor,
  borderColor,
  textColor,
  detail,
  detailKey,
}: {
  label: string;
  dotColor: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  detail?: string;
  detailKey: string;
}) {
  return (
    <div className="inline-flex flex-col items-start gap-1 max-w-full">
      <span
        style={{
          backgroundColor: bgColor,
          borderColor,
          color: textColor,
        }}
        className="inline-flex items-center justify-center gap-1.5 px-2.5 py-1 rounded-full border font-bold text-[11px] leading-none whitespace-nowrap shadow-2xs"
      >
        <svg
          width="7"
          height="7"
          viewBox="0 0 8 8"
          aria-hidden="true"
          className="shrink-0 block"
        >
          <circle cx="4" cy="4" r="4" fill={dotColor} />
        </svg>
        <span className="leading-none">{label}</span>
      </span>
      {detail ? (
        <span className="text-[11px] leading-snug text-slate-600 font-normal">
          {renderInline(detail, detailKey)}
        </span>
      ) : null}
    </div>
  );
}

function renderStatusCell(cellText: string, key: string): React.ReactNode {
  const plain = cellText.replace(/[*_`]+/g, "").trim();

  const condMatch = plain.match(/^(Условно соответствует|Требует уточнения|Требует сверки)(.*)$/i);
  if (condMatch) {
    const tail = condMatch[2].replace(/^[\s.:;—–-]+/, "").trim();
    return (
      <StatusPill
        label={condMatch[1].charAt(0).toUpperCase() + condMatch[1].slice(1)}
        dotColor="#f59e0b"
        bgColor="#fffbeb"
        borderColor="#fde68a"
        textColor="#92400e"
        detail={tail || undefined}
        detailKey={`${key}-det`}
      />
    );
  }

  const negMatch =
    plain.match(/^(Не соответствует|Отклонение|Не подходит)(.*)$/i) ||
    (/^нет$/i.test(plain) ? [plain, "Нет", ""] : null);
  if (negMatch) {
    const tail = (negMatch[2] || "").replace(/^[\s.:;—–-]+/, "").trim();
    return (
      <StatusPill
        label={negMatch[1].charAt(0).toUpperCase() + negMatch[1].slice(1)}
        dotColor="#ef4444"
        bgColor="#fef2f2"
        borderColor="#fecaca"
        textColor="#991b1b"
        detail={tail || undefined}
        detailKey={`${key}-det`}
      />
    );
  }

  const posMatch =
    plain.match(/^(Соответствует|Подтверждено)(.*)$/i) ||
    (/^да$/i.test(plain) ? [plain, "Да", ""] : null);
  if (posMatch) {
    const tail = (posMatch[2] || "").replace(/^[\s.:;—–-]+/, "").trim();
    return (
      <StatusPill
        label={posMatch[1].charAt(0).toUpperCase() + posMatch[1].slice(1)}
        dotColor="#10b981"
        bgColor="#ecfdf5"
        borderColor="#a7f3d0"
        textColor="#065f46"
        detail={tail || undefined}
        detailKey={`${key}-det`}
      />
    );
  }

  return renderInline(cellText, key);
}

function renderUnorderedKvBlock(
  kvItems: { label: string; value: string }[],
  keyPrefix: string
): React.ReactNode {
  return (
    <div
      key={keyPrefix}
      className="rounded-xl border border-slate-200 overflow-hidden bg-white divide-y divide-slate-200/80"
    >
      {kvItems.map((kv, nIdx) => (
        <div
          key={`${keyPrefix}-r-${nIdx}`}
          className="flex flex-col sm:flex-row sm:items-baseline text-[13px] leading-relaxed"
        >
          <div className="sm:w-56 lg:w-64 shrink-0 px-3.5 py-2 sm:py-2.5 bg-slate-50/85 font-bold text-slate-800 border-b sm:border-b-0 sm:border-r border-slate-200/70">
            {renderInline(kv.label, `${keyPrefix}-l-${nIdx}`)}
          </div>
          <div className="flex-1 min-w-0 px-3.5 py-2 sm:py-2.5 text-slate-700">
            {renderInline(kv.value, `${keyPrefix}-v-${nIdx}`)}
          </div>
        </div>
      ))}
    </div>
  );
}

function renderListBlocks(nodes: ListNode[], keyPrefix: string): React.ReactNode {
  if (nodes.length === 0) return null;

  const hasAnyChildren = nodes.some((n) => n.children.length > 0);
  const allUnorderedKv =
    !hasAnyChildren &&
    nodes.every((n) => !n.ordered && extractKeyValue(n.text) !== null);

  if (allUnorderedKv && nodes.length >= 2) {
    return renderUnorderedKvBlock(
      nodes.map((n) => extractKeyValue(n.text)!),
      `${keyPrefix}-kv`
    );
  }

  const allOrdered = nodes.every((n) => n.ordered);
  if (allOrdered && (hasAnyChildren || nodes.length >= 2)) {
    return (
      <div key={`${keyPrefix}-cards`} className="space-y-2.5">
        {nodes.map((node, nIdx) => (
          <div
            key={`${keyPrefix}-card-${nIdx}`}
            className="rounded-xl border border-slate-200/90 bg-slate-50/55 p-3.5 space-y-2"
          >
            <div className="flex items-start gap-2.5 text-[13px] leading-relaxed">
              <span
                style={{
                  backgroundColor: "#ecfdf5",
                  color: "#065f46",
                  borderColor: "#a7f3d0",
                }}
                className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-md border font-extrabold text-[11px] leading-none shrink-0 mt-0.5"
              >
                {node.numLabel || nIdx + 1}
              </span>
              <div className="flex-1 min-w-0 text-slate-800">
                {renderInline(node.text, `${keyPrefix}-ord-${nIdx}`)}
              </div>
            </div>
            {node.children.length > 0 ? (
              <div className="pl-7 space-y-1.5 border-l-2 border-teal-200/70 ml-2.5">
                {node.children.map((ch, cIdx) => (
                  <div
                    key={`${keyPrefix}-ch-${nIdx}-${cIdx}`}
                    className="flex items-start gap-2 text-[12.5px] text-slate-700 leading-relaxed"
                  >
                    {ch.ordered ? (
                      <span className="font-bold text-teal-800 shrink-0 min-w-[18px]">
                        {ch.numLabel}.
                      </span>
                    ) : (
                      <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
                    )}
                    <span className="flex-1 min-w-0">
                      {renderInline(ch.text, `${keyPrefix}-cht-${nIdx}-${cIdx}`)}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    );
  }

  const renderedSegments: React.ReactNode[] = [];
  let idx = 0;
  while (idx < nodes.length) {
    // Group 2+ contiguous childless "**Ключ:** значение" bullets into a 2-column summary table
    const kvRun: { label: string; value: string }[] = [];
    let scan = idx;
    while (scan < nodes.length) {
      const candidate = nodes[scan];
      const kv = !candidate.ordered && candidate.children.length === 0 ? extractKeyValue(candidate.text) : null;
      if (!kv) break;
      kvRun.push(kv);
      scan += 1;
    }
    if (kvRun.length >= 2) {
      renderedSegments.push(renderUnorderedKvBlock(kvRun, `${keyPrefix}-kvrun-${idx}`));
      idx = scan;
      continue;
    }

    const node = nodes[idx];
    const hasOrderedChildren = node.children.some((c) => c.ordered);
    if (hasOrderedChildren) {
      renderedSegments.push(
        <div
          key={`${keyPrefix}-grp-${idx}`}
          className="rounded-xl border border-slate-200/90 bg-slate-50/45 p-3.5 space-y-2.5"
        >
          <div className="text-[13px] font-semibold text-slate-900 leading-relaxed flex items-start gap-2">
            <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
            <span className="flex-1 min-w-0">
              {renderInline(node.text, `${keyPrefix}-grpt-${idx}`)}
            </span>
          </div>
          <div className="space-y-2 pl-2">
            {node.children.map((ch, cIdx) =>
              ch.ordered ? (
                <div
                  key={`${keyPrefix}-gch-${idx}-${cIdx}`}
                  className="rounded-lg border border-slate-200/80 bg-white p-2.5 flex items-start gap-2.5 text-[12.5px] text-slate-700 leading-relaxed"
                >
                  <span className="inline-flex items-center justify-center min-w-[20px] h-[20px] px-1 rounded bg-slate-100 text-slate-700 border border-slate-200 font-bold text-[11px] shrink-0 mt-0.5">
                    {ch.numLabel}
                  </span>
                  <span className="flex-1 min-w-0">
                    {renderInline(ch.text, `${keyPrefix}-gcht-${idx}-${cIdx}`)}
                  </span>
                </div>
              ) : (
                <div
                  key={`${keyPrefix}-gch-${idx}-${cIdx}`}
                  className="flex items-start gap-2 pl-3 text-[12.5px] text-slate-600 leading-relaxed"
                >
                  <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
                  <span className="flex-1 min-w-0">
                    {renderInline(ch.text, `${keyPrefix}-gcht-${idx}-${cIdx}`)}
                  </span>
                </div>
              )
            )}
          </div>
        </div>
      );
      idx += 1;
      continue;
    }

    const singleKv = !node.ordered && node.children.length === 0 ? extractKeyValue(node.text) : null;
    if (singleKv) {
      renderedSegments.push(
        <div
          key={`${keyPrefix}-singlekv-${idx}`}
          className="rounded-lg border border-slate-200/70 bg-slate-50/50 px-3 py-2 text-[13px] leading-relaxed"
        >
          <span className="font-bold text-slate-900">{singleKv.label}: </span>
          <span className="text-slate-700">
            {renderInline(singleKv.value, `${keyPrefix}-skvv-${idx}`)}
          </span>
        </div>
      );
      idx += 1;
      continue;
    }

    renderedSegments.push(
      <div key={`${keyPrefix}-li-${idx}`} className="space-y-1.5">
        <div className="flex items-start gap-2 text-[13px] text-slate-700 leading-relaxed">
          {node.ordered ? (
            <span className="font-bold text-teal-800 shrink-0 min-w-[18px]">
              {node.numLabel}.
            </span>
          ) : (
            <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
          )}
          <span className="flex-1 min-w-0">
            {renderInline(node.text, `${keyPrefix}-lit-${idx}`)}
          </span>
        </div>
        {node.children.length > 0 ? (
          <div className="pl-5 space-y-1.5 border-l-2 border-teal-200/70 ml-1.5">
            {node.children.map((ch, cIdx) => (
              <div
                key={`${keyPrefix}-lich-${idx}-${cIdx}`}
                className="flex items-start gap-2 text-[12.5px] text-slate-600 leading-relaxed"
              >
                <span className="text-teal-600 font-bold mt-0.5 select-none">•</span>
                <span className="flex-1 min-w-0">
                  {renderInline(ch.text, `${keyPrefix}-licht-${idx}-${cIdx}`)}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
    idx += 1;
  }

  return (
    <div key={`${keyPrefix}-list`} className="space-y-2.5">
      {renderedSegments}
    </div>
  );
}

function renderBodyLines(lines: string[], sectionKey: string): React.ReactNode[] {
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
      blocks.push(<hr key={`${sectionKey}-hr-${i}`} className="my-3 border-slate-200" />);
      i += 1;
      continue;
    }

    const subHeadingMatch = trimmed.match(/^(#{4,5})\s+(.+)$/);
    if (subHeadingMatch) {
      const subCallout = renderCalloutParagraph(subHeadingMatch[2], `${sectionKey}-subco-${i}`);
      if (subCallout) {
        blocks.push(subCallout);
      } else {
        blocks.push(
          <h5
            key={`${sectionKey}-subh-${i}`}
            className="text-xs sm:text-[13px] font-extrabold text-teal-900 pt-2 pb-1 border-b border-teal-100"
          >
            {renderInline(subHeadingMatch[2], `${sectionKey}-subh-${i}`)}
          </h5>
        );
      }
      i += 1;
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push(
        <div
          key={`${sectionKey}-bq-${i}`}
          className="rounded-xl border-l-4 border-teal-500 bg-teal-50/50 px-3.5 py-2.5 text-[13px] text-slate-800 leading-relaxed space-y-1"
        >
          {quoteLines.map((ql, qIdx) => (
            <p key={`${sectionKey}-bql-${i}-${qIdx}`}>{renderInline(ql, `${sectionKey}-bql-${i}-${qIdx}`)}</p>
          ))}
        </div>
      );
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
      const isTwoColKv = headers.length === 2;
      const tableMinWidthClass =
        headers.length >= 5
          ? "min-w-[680px]"
          : headers.length === 4
          ? "min-w-[540px]"
          : "";
      blocks.push(
        <TableScrollBox key={`${sectionKey}-tbl-${i}`}>
          <table className={`w-full ${tableMinWidthClass} text-left border-collapse text-xs`}>
            <thead className="bg-slate-100/95 text-slate-800 font-bold border-b border-slate-200">
              <tr>
                {headers.map((h, hIdx) => {
                  const lowerH = h.toLowerCase();
                  const isStatusCol =
                    lowerH.includes("статус") || lowerH.includes("соответств");
                  return (
                    <th
                      key={`th-${hIdx}`}
                      className={`px-3.5 py-2.5 align-top ${
                        isTwoColKv && hIdx === 0
                          ? "w-48 sm:w-60"
                          : isStatusCol
                          ? "min-w-[148px]"
                          : ""
                      }`}
                    >
                      {renderInline(h, `${sectionKey}-th-${i}-${hIdx}`)}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {rows.map((r, rIdx) => (
                <tr key={`tr-${rIdx}`} className={rIdx % 2 === 1 ? "bg-slate-50/50" : "bg-white"}>
                  {headers.map((_, cIdx) => {
                    const cellText = r[cIdx] ?? "";
                    return (
                      <td
                        key={`td-${rIdx}-${cIdx}`}
                        className={`px-3.5 py-2.5 align-top leading-relaxed ${
                          isTwoColKv && cIdx === 0
                            ? "font-bold text-slate-900 bg-slate-50/55"
                            : "text-slate-700"
                        }`}
                      >
                        {renderStatusCell(cellText, `${sectionKey}-td-${i}-${rIdx}-${cIdx}`)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </TableScrollBox>
      );
      continue;
    }

    if (/^(\*|-|•|\d+[.)])\s+/.test(trimmed)) {
      const nodes: ListNode[] = [];
      while (i < lines.length) {
        const curRaw = lines[i];
        const curTrim = curRaw.trim();
        const m = curTrim.match(/^(\*|-|•|(\d+)[.)])\s+(.+)$/);
        if (!m) break;
        const leadingSpaces = curRaw.length - curRaw.trimStart().length;
        const isOrdered = Boolean(m[2]);
        const numLabel = m[2] || "";
        const itemText = m[3];
        if (leadingSpaces >= 2 && nodes.length > 0) {
          nodes[nodes.length - 1].children.push({
            indent: leadingSpaces,
            ordered: isOrdered,
            numLabel,
            text: itemText,
          });
        } else {
          nodes.push({
            ordered: isOrdered,
            numLabel,
            text: itemText,
            children: [],
          });
        }
        i += 1;
      }
      blocks.push(renderListBlocks(nodes, `${sectionKey}-lst-${i}`));
      continue;
    }

    const callout = renderCalloutParagraph(trimmed, `${sectionKey}-co-${i}`);
    if (callout) {
      blocks.push(callout);
    } else {
      blocks.push(
        <p key={`${sectionKey}-p-${i}`} className="text-[13px] text-slate-700 leading-relaxed">
          {renderInline(trimmed, `${sectionKey}-p-${i}`)}
        </p>
      );
    }
    i += 1;
  }

  return blocks;
}

type ReportSection = {
  heading: string | null;
  level: number;
  lines: string[];
};

export function SafeMarkdownView({ markdown }: { markdown: string }) {
  const allLines = (markdown || "").replace(/\r\n/g, "\n").split("\n");
  const sections: ReportSection[] = [];
  let current: ReportSection = { heading: null, level: 0, lines: [] };

  for (let idx = 0; idx < allLines.length; idx += 1) {
    const line = allLines[idx];
    const trimmed = line.trim();
    const majorMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (majorMatch) {
      if (current.heading !== null || current.lines.some((l) => l.trim() && !/^(-{3,}|\*{3,}|_{3,})$/.test(l.trim()))) {
        sections.push(current);
      }
      current = {
        heading: majorMatch[2].trim(),
        level: majorMatch[1].length,
        lines: [],
      };
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      let nextIdx = idx + 1;
      while (nextIdx < allLines.length && !allLines[nextIdx].trim()) {
        nextIdx += 1;
      }
      if (nextIdx >= allLines.length || /^#{1,3}\s+/.test(allLines[nextIdx].trim())) {
        continue;
      }
    }

    current.lines.push(line);
  }

  if (current.heading !== null || current.lines.some((l) => l.trim())) {
    sections.push(current);
  }

  if (sections.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4 min-w-0">
      {sections.map((section, sIdx) => {
        const bodyBlocks = renderBodyLines(section.lines, `sec-${sIdx}`);
        if (!section.heading) {
          return (
            <div
              key={`sec-${sIdx}`}
              className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 shadow-2xs space-y-3 min-w-0"
            >
              {bodyBlocks}
            </div>
          );
        }

        const numMatch = section.heading.match(/^(\d+)[.)]\s+(.+)$/);
        const sectionNumber = numMatch ? numMatch[1] : null;
        const sectionTitle = numMatch ? numMatch[2] : section.heading;

        return (
          <section
            key={`sec-${sIdx}`}
            className="rounded-2xl border border-slate-200 bg-white shadow-2xs min-w-0"
          >
            <header className="px-4 sm:px-5 py-3 rounded-t-2xl bg-gradient-to-r from-emerald-50/90 via-teal-50/65 to-slate-50 border-b border-teal-100/90 flex items-center gap-2.5">
              {sectionNumber ? (
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-lg bg-teal-600 text-white text-xs font-extrabold shrink-0 shadow-2xs">
                  {sectionNumber}
                </span>
              ) : null}
              <h4 className="text-sm sm:text-[15px] font-extrabold text-slate-900 leading-snug">
                {renderInline(sectionTitle, `sec-h-${sIdx}`)}
              </h4>
            </header>
            {bodyBlocks.length > 0 ? (
              <div className="p-4 sm:p-5 space-y-3 min-w-0">{bodyBlocks}</div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
