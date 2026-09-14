import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TenderLex",
    short_name: "TenderLex",
    description: "Поиск поставщиков, подготовка запроса коммерческого предложения и анализ закупок.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#00666b",
    lang: "ru-RU",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "120x120",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/favicon.png",
        sizes: "120x120",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/apple-touch-icon.png",
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
