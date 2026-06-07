import type { Metadata } from "next";

import { CabinetClient } from "./cabinet-client";

export const metadata: Metadata = {
  title: "Личный кабинет",
  robots: {
    index: false,
    follow: false,
  },
};

export default function CabinetPage() {
  return <CabinetClient />;
}
