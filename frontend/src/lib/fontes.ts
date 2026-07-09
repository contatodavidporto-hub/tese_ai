// Segunda instância do Newsreader — SÓ itálico (P1, CORRECOES-RODADA-1.md).
//
// O layout raiz (src/app/layout.tsx) carrega o Newsreader com `style:
// ["normal"]`: o arquivo itálico (147 kB) deixou de ser preloadado em TODA
// rota. Esta instância separada existe só para as rotas que realmente
// renderizam itálico — `/tese` (Markdown.tsx: <em>/*itálico* do markdown e a
// voz narrada da D5) e `/como-funciona` (parágrafo narrado da cláusula 05).
//
// next/font gera uma família CSS interna PRÓPRIA por instância, mesmo que
// nenhum `variable` seja repetido — por isso esta fonte só existe onde for
// explicitamente importada e sua `.variable` aplicada a um elemento
// ancestral (ex.: o <main> da página). Onde isso não acontece, a CSS var
// `--font-newsreader-italico` fica indefinida e o utilitário
// `font-display-italico` (globals.css) não resolve — o que é o
// comportamento seguro: itálico só onde foi explicitamente ligado.
//
// ATENÇÃO faux-italic: sempre combine `font-display-italico` (família) com a
// utilidade `italic` do Tailwind (estilo) — só a família não força
// `font-style: italic`, e só o estilo sem a família certa faz o navegador
// sintetizar um oblíquo falso a partir do Newsreader normal.
import { Newsreader } from "next/font/google";

export const newsreaderItalico = Newsreader({
  variable: "--font-newsreader-italico",
  subsets: ["latin"],
  style: ["italic"],
  // `axes` só é aceito quando `weight` fica no padrão variável (next/font
  // recusa combinar `axes` com um `weight` fixo — o eixo `wght` precisa
  // continuar variável para conviver com o eixo extra `opsz`). O peso 500
  // da voz da D5 vem do `font-medium` do Tailwind (font-weight: 500) na
  // hora de usar, não daqui.
  axes: ["opsz"],
  display: "swap",
});
