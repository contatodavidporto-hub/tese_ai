"use client";

// LinkCinema — <Link> do Next com a "virada de página do jornal": véu de
// SAÍDA (#veu-rota-saida, scaleY 0→1 de baixo, 200ms) + flag de sessionStorage
// que arma o véu de ENTRADA do template.tsx na rota de destino.
// Missão MATÉRIA VIVA, Onda 1D (plano §3 crit.5 + emendas R2/R3/R10).
//
// R2 (LEI): este arquivo é JS puro — ZERO gsap (véus são keyframes CSS em
// cinema/rotas.css, ligados só por classList). Header/Footer podem importá-lo
// sem arrastar motor de animação para nenhuma rota (first-load de /tese
// ≤ +3KB é gate de merge).
//
// MATRIZ DE BYPASS (completa — nesses casos o clique segue o caminho padrão
// do <Link>/navegador, sem véu e sem flag):
//   - onClick do consumidor já fez preventDefault;
//   - botão não-principal (o botão do meio dispara auxclick, não click — e
//     sem preventDefault o navegador abre a nova aba normalmente);
//   - modificadores ctrl/cmd/shift/alt (nova aba/janela/download);
//   - target (≠ _self) ou download no próprio link;
//   - href cross-origin (o Link já degrada para navegação plena);
//   - âncora dentro da MESMA página (só hash muda): scroll nativo do Link;
//   - MESMA URL (pathname+search iguais, sem hash novo): NADA — não anima,
//     não navega duplo (preventDefault e fim);
//   - destino /tese: router.push DIRETO, SEM véu de saída E SEM flag de
//     entrada — o véu especializado .virada-edicao permanece lá (R10);
//   - prefers-reduced-motion: push imediato SEM véu de saída (a flag de
//     entrada ainda é setada — o template reduz a entrada a um fade 120ms
//     via CSS, registro nominal em cinema/rotas.css);
//   - clique duplo / novo clique durante a saída: NÃO empilha (guard pela
//     própria classe .veu-rota-saindo no overlay; o pointer-events:auto do
//     véu em animação é o cinto-e-suspensório para cliques de mouse).
//
// SEMPRE NAVEGA: router.push no animationend, com animationcancel e um
// timeout de segurança de 240ms como redes (o que vier primeiro). Se outra
// navegação mudou a URL durante a animação (popstate/voltar — R3), a
// intenção mais recente vence: o push é abortado em vez de atropelar o back.
//
// Sem JS: renderiza um <Link> normal (href real no <a>) + @view-transition
// CSS do globals.css. prefetch do next/link preservado (repassado intacto).

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentPropsWithoutRef, MouseEvent } from "react";

// Flag lida-e-limpa pelo template.tsx do raiz — manter em sincronia.
const CHAVE_VEU_ROTA = "tese-ai:veu-rota";
const CLASSE_SAIDA = "veu-rota-saindo";
const TIMEOUT_SEGURANCA_MS = 240;

type PropsLinkCinema = Omit<ComponentPropsWithoutRef<typeof Link>, "href"> & {
  /** Só string (nav interna do site) — UrlObject fica com o <Link> puro. */
  href: string;
};

function marcarVeuEntrada(destino: string): void {
  try {
    // Guarda o PATHNAME do destino: se a navegação abortar (falha de fetch
    // do App Router), a flag órfã não dispara véu espúrio numa remontagem
    // futura de OUTRA rota (popstate/refresh — R10; auditoria 2026-07-13,
    // achado 9). O template só anima se location.pathname casar.
    window.sessionStorage.setItem(
      CHAVE_VEU_ROTA,
      new URL(destino, window.location.origin).pathname,
    );
  } catch {
    // sessionStorage indisponível: navega sem véu de entrada (o template
    // simplesmente não encontra a flag).
  }
}

export function LinkCinema({
  href,
  onClick,
  target,
  download,
  ...resto
}: PropsLinkCinema) {
  const router = useRouter();

  function aoClicar(evento: MouseEvent<HTMLAnchorElement>) {
    // Contrato do próprio next/link: onClick do consumidor roda primeiro e
    // pode cancelar tudo.
    onClick?.(evento);
    if (evento.defaultPrevented) return;

    // ---- matriz de bypass (retornar SEM preventDefault delega ao <Link>,
    // que já trata modificadores/target/cross-origin corretamente) ----
    if (evento.button !== 0) return;
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey)
      return;
    if (target && target !== "_self") return;
    if (download !== undefined) return;

    let destino: URL;
    try {
      destino = new URL(href, window.location.href);
    } catch {
      return; // href inválida: comportamento padrão
    }
    if (destino.origin !== window.location.origin) return;

    const mesmaBase =
      destino.pathname === window.location.pathname &&
      destino.search === window.location.search;
    if (mesmaBase) {
      // Âncora na própria página: scroll nativo do Link, sem véu.
      if (destino.hash) return;
      // MESMA URL: nada — não anima, não navega duplo (R3).
      evento.preventDefault();
      return;
    }

    // Daqui em diante a navegação é nossa.
    evento.preventDefault();

    const alvo = destino.pathname + destino.search + destino.hash;
    const veu = document.getElementById("veu-rota-saida");

    // Guard de clique duplo / navegação já em curso: não empilha (R3). O
    // VeuRotas remove a classe a cada troca de rota, rearmando o guard.
    if (veu?.classList.contains(CLASSE_SAIDA)) return;

    // Destino /tese: push direto, SEM véu de saída e SEM flag de entrada —
    // o véu .virada-edicao especializado permanece lá (TeseClient intocado).
    // Comparação exata + prefixo com barra ("/teses" NÃO é "/tese").
    if (destino.pathname === "/tese" || destino.pathname.startsWith("/tese/")) {
      router.push(alvo);
      return;
    }

    // Reduce: push imediato sem véu de saída; a flag de entrada vale (o
    // template reduz a entrada a fade 120ms via CSS). Idem se o overlay não
    // existir por qualquer razão — a navegação nunca depende da cortina.
    if (
      !veu ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      marcarVeuEntrada(href);
      router.push(alvo);
      return;
    }

    // ---- saída cinematográfica ----
    const origem = window.location.pathname + window.location.search;
    let concluido = false;
    let timer = 0;

    const concluir = () => {
      if (concluido) return;
      concluido = true;
      window.clearTimeout(timer);
      veu.removeEventListener("animationend", concluir);
      veu.removeEventListener("animationcancel", concluir);
      // R3 (popstate durante a animação): se OUTRA navegação já mudou a URL
      // (voltar/avançar), a intenção mais recente vence — abortamos o push;
      // o VeuRotas desarma o véu na troca de rota. Senão, navega SEMPRE.
      if (window.location.pathname + window.location.search !== origem) return;
      marcarVeuEntrada(href);
      router.push(alvo);
    };

    veu.addEventListener("animationend", concluir);
    veu.addEventListener("animationcancel", concluir);
    timer = window.setTimeout(concluir, TIMEOUT_SEGURANCA_MS);
    veu.classList.add(CLASSE_SAIDA);
  }

  return (
    <Link
      href={href}
      target={target}
      download={download}
      onClick={aoClicar}
      {...resto}
    />
  );
}
