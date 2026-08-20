"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  BookOpen,
  ArrowRight,
  Clock,
  Calendar,
  Sparkles,
  Factory,
  FileText,
  ShieldCheck,
  Calculator,
  UserCheck,
  Layers,
  ChevronRight,
  TrendingDown,
} from "lucide-react";
import {
  KNOWLEDGE_ARTICLES,
  KNOWLEDGE_CATEGORIES,
  type KnowledgeArticleMeta,
} from "@/data/knowledge-base";

export function KnowledgeBaseHubClient() {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const filteredArticles = useMemo(() => {
    return KNOWLEDGE_ARTICLES.filter((article) => {
      return selectedCategory === "all" || article.category === selectedCategory;
    });
  }, [selectedCategory]);

  const featuredArticles = useMemo(() => {
    return KNOWLEDGE_ARTICLES.filter((a) => a.featured).slice(0, 2);
  }, []);

  return (
    <div className="space-y-10">
      {/* CATEGORY PILLS (NO SEARCH BAR) */}
      <div className="flex flex-wrap items-center justify-center gap-2 max-w-5xl mx-auto">
        {KNOWLEDGE_CATEGORIES.map((cat) => {
          const isActive = selectedCategory === cat.id;
          const count =
            cat.id === "all"
              ? KNOWLEDGE_ARTICLES.length
              : KNOWLEDGE_ARTICLES.filter((a) => a.category === cat.id).length;

          return (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all ${
                isActive
                  ? "bg-[#075b63] text-white shadow-md shadow-[#075b63]/20 scale-102"
                  : "bg-white text-[#172120] hover:bg-[#e5f4f3] hover:text-[#075b63] border border-[#d8e3e1]"
              }`}
            >
              <span>{cat.label}</span>
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-black ${
                  isActive
                    ? "bg-[#06464c] text-[#e5f4f3]"
                    : "bg-[#eef3f2] text-[#697a77]"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* FEATURED SPOTLIGHT (LIGHT GREEN / WHITE STYLING - NO DARK CARDS) */}
      {selectedCategory === "all" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#075b63]">
            <Sparkles size={15} className="text-[#075b63]" />
            <span>Главные руководства закупщика</span>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {featuredArticles.map((article) => (
              <Link
                key={article.slug}
                href={`/baza-znaniy/${article.slug}`}
                className="group relative flex flex-col justify-between p-6 sm:p-8 rounded-3xl bg-white hover:bg-[#f6f8f7] text-[#172120] shadow-xs hover:shadow-md transition-all border-2 border-[#d8e3e1] hover:border-[#075b63]"
              >
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-block px-3 py-1 text-xs font-black uppercase tracking-wider text-[#075b63] bg-[#e5f4f3] border border-[#b8c8c5] rounded-lg">
                      {article.tag}
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-xs text-[#697a77] font-semibold">
                      <Clock size={13} className="text-[#075b63]" />
                      {article.readTime}
                    </span>
                  </div>

                  <h3 className="text-xl sm:text-2xl font-black tracking-tight text-[#172120] group-hover:text-[#075b63] transition-colors leading-snug">
                    {article.title}
                  </h3>

                  <p className="text-[#2f3f3d] text-xs sm:text-sm leading-relaxed line-clamp-3">
                    {article.subtitle}
                  </p>
                </div>

                <div className="pt-6 flex items-center justify-between text-xs font-bold text-[#075b63] border-t border-[#d8e3e1] mt-6">
                  <span>Читать руководство</span>
                  <ArrowRight
                    size={16}
                    className="group-hover:translate-x-1 transition-transform"
                  />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ALL ARTICLES GRID (CLEAN LIGHT/WHITE DESIGN) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg sm:text-xl font-black text-[#172120] tracking-tight">
            {selectedCategory === "all"
              ? `Все статьи (${filteredArticles.length})`
              : `${KNOWLEDGE_CATEGORIES.find((c) => c.id === selectedCategory)?.label} (${filteredArticles.length})`}
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredArticles.map((article) => (
            <Link
              key={article.slug}
              href={`/baza-znaniy/${article.slug}`}
              className="group flex flex-col justify-between p-5 sm:p-6 rounded-2xl bg-white hover:bg-[#f6f8f7] border border-[#d8e3e1] hover:border-[#075b63] shadow-2xs hover:shadow-md transition-all"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-black uppercase tracking-wider text-[#075b63] bg-[#e5f4f3] px-2.5 py-0.5 rounded-md">
                    {article.tag}
                  </span>
                  <span className="text-[11px] text-[#697a77] font-medium flex items-center gap-1">
                    <Clock size={11} className="text-[#075b63]" />
                    {article.readTime}
                  </span>
                </div>

                <h3 className="font-black text-[#172120] text-base group-hover:text-[#075b63] transition-colors leading-snug line-clamp-2">
                  {article.title}
                </h3>

                <p className="text-xs text-[#2f3f3d] leading-relaxed line-clamp-3">
                  {article.description}
                </p>
              </div>

              <div className="pt-4 mt-4 border-t border-[#d8e3e1] flex items-center justify-between text-xs font-bold text-[#075b63]">
                <span>Открыть статью</span>
                <ChevronRight
                  size={14}
                  className="group-hover:translate-x-1 transition-transform"
                />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
