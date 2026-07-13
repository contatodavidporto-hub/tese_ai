import type { MetadataRoute } from "next";

// Manifest da casa (missão APOTEOSE, onda META — LEI §3.1 + veredito-marca §4.9).
// `theme_color`/`background_color` = --bg-page claro (#f6f6f3), coerente com o
// `viewport.themeColor` claro do layout raiz (o manifest aceita UM valor; o par
// claro/escuro vive no viewport). Ícones 192/512 gerados pelo harness
// `.maestro/ferramentas/gera_og.py` (chip de papel/joia sobre #f6f6f3 OPACO,
// símbolo na zona segura central de 80% — serve `any` e `maskable`; o tipo do
// Next não aceita "any maskable" combinado, então declaramos os dois purposes
// apontando para o mesmo PNG). Servido same-origin: CSP diff-zero
// (manifest-src herda default-src 'self').
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tese AI",
    short_name: "Tese AI",
    description:
      "Teses de investimento estruturadas e rastreáveis, com a fonte de cada número. Ferramenta de análise — não é recomendação de investimento.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f6f3",
    theme_color: "#f6f6f3",
    icons: [
      {
        src: "/icone-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icone-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icone-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icone-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
