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
// - Passiva e rAF-coalescida; ResizeObserver (não listener de resize) +
//   fonts.ready (a fonte com display:swap muda a altura DEPOIS do 1º paint).
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

    let frame = 0;
    // Escreve só quando o valor MUDA de verdade (>=0,5px): reescrita idêntica
    // não custa layout, mas o guard mantém o log de perf limpo e evita
    // qualquer chance de loop de observação.
    const ultimo = new Map<string, number>();

    const medir = () => {
      frame = 0;
      for (const { el, prop } of observados) {
        const altura = el.getBoundingClientRect().height;
        if (altura <= 0) continue; // elemento oculto (ex.: error boundary)
        const anterior = ultimo.get(prop);
        if (anterior !== undefined && Math.abs(anterior - altura) < 0.5) continue;
        ultimo.set(prop, altura);
        raiz.style.setProperty(prop, `${altura}px`);
      }
    };

    const agendar = () => {
      if (frame) return;
      frame = requestAnimationFrame(medir);
    };

    const ro = new ResizeObserver(agendar);
    for (const { el } of observados) ro.observe(el);

    // A fonte com display:swap troca depois do 1º paint e muda a altura real.
    document.fonts?.ready.then(agendar).catch(() => {});

    agendar();

    return () => {
      if (frame) cancelAnimationFrame(frame);
      ro.disconnect();
      // Devolve o controle às vars estáticas do CSS (o default de first-paint).
      for (const { prop } of observados) raiz.style.removeProperty(prop);
    };
  }, []);

  return null;
}
