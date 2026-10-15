import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Лаборатория кнопок и стратегий | TenderLex UI Lab",
  robots: {
    index: false,
    follow: false,
  },
};

export default function TestButtonsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
