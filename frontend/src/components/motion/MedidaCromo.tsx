"use client";

// MEDIDA DO CROMO (missão HORIZONTE, Onda 0 — emenda E4c do red-team).
//
// PROBLEMA QUE ESTA ILHA RESOLVE: a capa (#hero), a cena do nascimento
// (sticky) e o Salão (pin) precisam saber quanto do topo da tela a Tarja e o
// Header já ocupam. As custom properties `--altura-tarja`/`--altura-header`
// declaram esses valores em degraus (globals.css), calibrados nos platôs
// REAIS de wrap — exatos no first-paint, CLS zero. Mas o gate E4 provou que
// sob **zoom de texto 200%** (WCAG 1.4.4) e **text-spacing** (1.4.12) o texto
// reflui e os platôs mudam de forma não-linear: a divergência chegou a
// +180px na Tarja. Com a var subestimada, a cena sticky desliza POR BAIXO da
// Tarja (conteúdo ocluído) e o pin do Salão fica mais alto que o espaço
// disponível (base das bolhas clipada).
//
// CONTRATO (o que esta ilha é e o que ela NÃO é):
// - Ela NÃO altera nenhuma propriedade computada da Tarja/Header (§1.5 da
//   lei: o chrome é intocado). Só MEDE e publica a altura que eles já têm.
// - Escrita SÓ por CSSOM (`setProperty` em documentElement) — zero <style>,
//   zero style={} JSX. CSP intacta.
// - A var estática do CSS é o DEFAULT de first-paint; esta ilha é o BACKSTOP
//   de correção. No caso comum (zoom 100%, espaçamento padrão) ela reescreve
//   o mesmo valor que já estava lá -> nenhum shift, CLS permanece zero.
// - Passiva e de layout ZERO: o valor vem do `borderBoxSize` do próprio
//   ResizeObserver (nunca getBoundingClientRect/rAF — ver §PERF-B2 abaixo). O
//   RO já cobre a observação inicial, o swap da fonte (display:swap muda a
//   altura DEPOIS do 1º paint), o zoom de texto e o text-spacing.
// - Renderiza null. Montada só onde as vars são consumidas (landing) — /tese
//   e as demais rotas não pagam este byte.

import { useLayoutEffect } from "react";

// Os seletores são os MESMOS que o pin do Salão usa para medir o `start`
// (o aria-label da Tarja é pré-condição de grep na lei da missão).
const SEL_TARJA = '[role="note"][aria-label="Aviso regulatório"]';
const SEL_HEADER = "header";

type Alvo = { seletor: string; prop: string };

const ALVOS: readonly Alvo[] = [
  { seletor: SEL_TARJA, prop: "--altura-tarja" },
  { seletor: SEL_HEADER, prop: "--altura-header" },
];

export function MedidaCromo(): null {
  useLayoutEffect(() => {
    const raiz = document.documentElement;
    const observados = ALVOS.map(({ seletor, prop }) => {
      const el = document.querySelector<HTMLElement>(seletor);
      return el ? { el, prop } : null;
    }).filter((x): x is { el: HTMLElement; prop: string } => x !== null);

    if (observados.length === 0) return;


    // Escreve só quando o valor MUDA de verdade (>=0,5px).
    const ultimo = new Map<string, number>();

    // ⚠ PERF — B2 (2026-07-14): SEMEAR ESTE CACHE É O QUE HONRA O CONTRATO.
    // Sem a semente o Map nasce VAZIO e a PRIMEIRA passada escreve SEMPRE —
    // inclusive no caso comum (zoom 100%), em que a medida bate com o token
    // estático e a escrita é semanticamente um no-op. E não existe no-op aqui:
    // escrever uma custom property HERDADA em documentElement invalida o
    // estilo do DOCUMENTO INTEIRO. Medido no gate de TBT (mobile-4x, landing,
    // `.maestro/evidencias/onda5/B2-perf/`): esta escrita custava um recalc de
    // estilo completo + um segundo layout completo e, pior, deixava o layout
    // SUJO para o próximo leitor do mesmo quadro (FioDaFonte lê
    // `pai.clientWidth` no rAF seguinte) — que então pagava OUTRO layout
    // forçado. Dois layouts inteiros por quadro, ~80ms no perfil 4x.
    // Semeado, o caso comum não escreve NADA: a var estática do CSS segue dona
    // do first-paint (é exatamente o que o CONTRATO acima já prometia — "no
    // caso comum ela reescreve o mesmo valor -> nenhum shift"). O BACKSTOP
    // continua intacto: sob zoom 200%/text-spacing o valor DIVERGE de verdade
    // e a escrita acontece, como antes.
    // Os tokens são declarados em `rem` (globals.css §alturas) — resolver a
    // unidade é obrigatório para a comparação ser em px de verdade. Unidade
    // inesperada => não semeia => degrada para o comportamento antigo.
    const cssRaiz = getComputedStyle(raiz);
    const pxDaRaiz = Number.parseFloat(cssRaiz.fontSize) || 16;
    const emPx = (declarado: string): number => {
      const txt = declarado.trim();
      const n = Number.parseFloat(txt);
      if (!Number.isFinite(n)) return Number.NaN;
      if (txt.endsWith("rem")) return n * pxDaRaiz;
      if (txt.endsWith("px")) return n;
      return Number.NaN;
    };
    for (const { prop } of observados) {
      const jaDeclarado = emPx(cssRaiz.getPropertyValue(prop));
      if (Number.isFinite(jaDeclarado)) ultimo.set(prop, jaDeclarado);
    }

    // ⚠ PERF — B2: A ALTURA VEM DE GRAÇA COM O ResizeObserver.
    // Era `getBoundingClientRect()` dentro de um rAF. Um gBCR num quadro de
    // load FORÇA layout síncrono da página inteira: medido no perfil 4x, as 4
    // chamadas (2 passadas × 2 alvos) custavam ~47ms de layout forçado — a
    // maior fatia isolada do excedente de TBT da landing.
    // O ResizeObserver JÁ ENTREGA a caixa medida (`borderBoxSize`), calculada
    // pelo próprio ciclo de layout do navegador: ler dali é layout ZERO. E ele
    // dispara exatamente quando o contrato precisa — na observação inicial, no
    // swap da fonte (`display:swap` muda a altura real), sob zoom de texto
    // 200% e sob text-spacing. Por isso o rAF, o gBCR e o gancho de
    // `fonts.ready` saíram: eram três caminhos para o que o RO já faz sozinho,
    // e o único que custava layout era o nosso.
    // `blockSize` (eixo de bloco) = a altura em `horizontal-tb`, e — melhor que
    // o gBCR — é a caixa de LAYOUT, imune a transform (a trava C2 já proíbe
    // transform em ancestral da régua, mas a medida agora é correta por
    // construção, não por convenção).
    const propPorAlvo = new Map<Element, string>(
      observados.map(({ el, prop }) => [el, prop]),
    );

    const ro = new ResizeObserver((entradas) => {
      for (const entrada of entradas) {
        const prop = propPorAlvo.get(entrada.target);
        if (!prop) continue;
        const caixa = entrada.borderBoxSize?.[0];
        // Fallback só para engine sem `borderBoxSize` (pré-2021): aí sim gBCR
        // — `contentRect` NÃO serve (exclui padding/borda, e a Tarja tem os dois).
        const altura = caixa
          ? caixa.blockSize
          : entrada.target.getBoundingClientRect().height;
        if (altura <= 0) continue; // elemento oculto (ex.: error boundary)
        const anterior = ultimo.get(prop);
        if (anterior !== undefined && Math.abs(anterior - altura) < 0.5) continue;
        ultimo.set(prop, altura);
        raiz.style.setProperty(prop, `${altura}px`);
      }
    });
    for (const { el } of observados) ro.observe(el);

    return () => {
      ro.disconnect();
      // Devolve o controle às vars estáticas do CSS (o default de first-paint).
      for (const { prop } of observados) raiz.style.removeProperty(prop);
    };
  }, []);

  return null;
}
