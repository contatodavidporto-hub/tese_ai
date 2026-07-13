"use client";

// template.tsx do raiz — véu de ENTRADA de rota ("a nova edição abre de
// cima"). Missão MATÉRIA VIVA, Onda 1D (plano §3 crit.5 + emenda R10).
//
// Por que um template: o App Router REMONTA o template a cada navegação —
// é o gancho canônico para uma entrada de rota sem tocar em nenhuma página.
// `children` chega como prop (payload server-rendered): marcar este arquivo
// como client NÃO arrasta as páginas para o bundle do cliente.
//
// R10 (DECISÃO do plano): o véu é GATEADO por uma flag de sessionStorage que
// só o LinkCinema seta, imediatamente antes do router.push. Aqui a flag é
// lida-e-limpa no mount e o véu SÓ roda se ela existir. Consequências:
//   - primeira carga / refresh: sem cortina (LCP intacto — o véu nasce
//     display:none no CSS; SSR jamais emite conteúdo coberto);
//   - popstate / voltar-avançar: sem véu (a flag nunca foi setada);
//   - /tese: sem véu duplo (o LinkCinema não seta a flag para /tese — o véu
//     especializado .virada-edicao permanece lá).
//
// Trava C2: o véu é um IRMÃO do conteúdo (fixed, z-40 < Tarja z-50 <
// .regua-leitura z-55) e anima o PRÓPRIO transform — nenhum wrapper de
// conteúdo é animado, nenhum ancestral de .regua-leitura ganha transform.
//
// CSP: estado dinâmico só via classList (.veu-rota-ativa); zero style=
// inline, zero gsap neste arquivo (R2). Coreografia em cinema/rotas.css
// (reduce = fade 120ms, registrado nominalmente lá).

import { useEffect, useLayoutEffect, useRef } from "react";

// Flag setada pelo LinkCinema (src/components/motion/LinkCinema.tsx) —
// manter os dois lados em sincronia.
const CHAVE_VEU_ROTA = "tese-ai:veu-rota";

// useLayoutEffect no cliente (ativa o véu ANTES do primeiro paint da rota
// nova — sem frame de conteúdo descoberto); useEffect no servidor só para
// silenciar o aviso de SSR do React (não roda de verdade lá).
const useLayoutEffectIsomorfo =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export default function Template({ children }: { children: React.ReactNode }) {
  const veuRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffectIsomorfo(() => {
    let flag: string | null = null;
    try {
      flag = window.sessionStorage.getItem(CHAVE_VEU_ROTA);
      if (flag !== null) window.sessionStorage.removeItem(CHAVE_VEU_ROTA);
    } catch {
      // sessionStorage indisponível (modo privado restrito): sem véu — a
      // navegação em si nunca depende da cortina.
    }
    if (flag === null) return;
    // R10 + achado 9: flag órfã (navegação anterior abortada) não pode virar
    // véu num popstate/refresh — só anima se ESTA rota é o destino marcado.
    if (flag !== window.location.pathname) return;

    const veu = veuRef.current;
    if (!veu) return;

    // Desarma ao terminar (volta a display:none — DOM limpo). O
    // animationcancel cobre aborto no meio (ex.: preferências de motion
    // mudando com a animação em curso).
    const desarmar = () => veu.classList.remove("veu-rota-ativa");
    veu.addEventListener("animationend", desarmar, { once: true });
    veu.addEventListener("animationcancel", desarmar, { once: true });
    veu.classList.add("veu-rota-ativa");

    return () => {
      veu.removeEventListener("animationend", desarmar);
      veu.removeEventListener("animationcancel", desarmar);
    };
    // Roda 1x por mount — e o template REMONTA a cada navegação (contrato
    // do App Router), então cada rota nova relê a flag.
  }, []);

  return (
    <>
      {/* Véu como IRMÃO do conteúdo, nunca wrapper (trava C2). aria-hidden:
          puramente decorativo; pointer-events:none no CSS. */}
      <div ref={veuRef} aria-hidden="true" className="veu-rota" />
      {children}
    </>
  );
}
