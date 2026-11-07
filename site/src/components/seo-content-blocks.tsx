import { CheckCircle2 } from "lucide-react";

export type SeoContentSection = {
  title: string;
  paragraphs: string[];
  bullets?: string[];
  note?: string;
};

export function SeoContentBlocks({ sections }: { sections: SeoContentSection[] }) {
  return (
    <section className="py-16 sm:py-24 border-b border-slate-200 bg-white">
      <div className="container max-w-4xl mx-auto px-4 sm:px-6">
        <div className="space-y-14">
          {sections.map((section) => (
            <article key={section.title} className="space-y-4">
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">{section.title}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph} className="text-sm sm:text-base text-slate-600 leading-relaxed font-medium">
                  {paragraph}
                </p>
              ))}
              {section.bullets ? (
                <ul className="grid sm:grid-cols-2 gap-3 pt-2">
                  {section.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-2.5 text-sm text-slate-700 font-medium leading-relaxed">
                      <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-teal-600" aria-hidden="true" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {section.note ? (
                <p className="pt-1 text-xs text-slate-500 leading-relaxed">{section.note}</p>
              ) : null}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
