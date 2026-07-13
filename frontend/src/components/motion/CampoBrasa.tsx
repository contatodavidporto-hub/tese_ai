"use client";

import { useEffect, useRef, useState } from "react";

import { MQ_REDUCE, ehReduce } from "@/lib/gsapSetup";

/**
 * CampoBrasa — gate de montagem da "Câmara de Brasa" (missão MATÉRIA VIVA,
 * plano §3 crit.1/crit.6 + emendas R6/R12b/R12c — Onda 1A).
 *
 * Este componente é SÓ o porteiro: o motor WebGL + shader vivem em
 * `campoBrasa.frag.ts` e chegam por `import()` DINÂMICO — quem reprova nos
 * gates NEM BAIXA o chunk (R12b). Gates, na ordem:
 *
 *   1. `prefers-reduced-motion: reduce` → não monta (e desmonta ao vivo se o
 *      usuário ligar depois — WCAG 2.3.3);
 *   2. `pointer: coarse` + `deviceMemory < 4` → não monta (celular fraco);
 *   3. probe de WebGL 1 falhou → não monta.
 *
 * Tudo agendado em `requestIdleCallback` com timeout 800ms e fallback
 * `setTimeout` para Safari (R12b) — o hero é LCP: o canvas é transparente,
 * chega DEPOIS do idle e jamais atrasa o primeiro paint (o H1 nunca depende
 * dele). Fallback de quem não monta = aurora enriquecida estática
 * (`cinema/luz.css`) — a produção atual, digna por contrato.
 *
 * `webglcontextlost` no motor → `aoPerderContexto` → desmonta limpo (sem
 * tentativa de restore; o fundo volta a ser a aurora CSS).
 *
 * Uso (Onda 2): filho direto do hero `.tem-foco`, IRMÃO do conteúdo (nunca
 * wrapper), depois do `.glifo-fantasma` e antes do `<FocoLuz/>` — camadas
 * z-index:-1 pintam na ordem do DOM (glifo no fundo, canvas, luz por cima).
 * CSP: zero `style=`; o posicionamento do canvas é da classe `.campo-brasa`
 * (cinema/hero.css); `width`/`height` de canvas são ATRIBUTOS de backing
 * store, não estilo.
 */

type NavegadorComMemoria = Navigator & { deviceMemory?: number };

/** R12b: requestIdleCallback com fallback setTimeout (Safari). */
function agendarOcioso(cb: () => void, timeoutMs: number): () => void {
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(cb, { timeout: timeoutMs });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(cb, 800); // mesmo budget do timeout do rIC
  return () => window.clearTimeout(id);
}

/** Gates de montagem — roda ANTES de qualquer import() (nem baixa o chunk). */
function passaNosGates(): boolean {
  if (ehReduce()) return false;
  const grosso = window.matchMedia("(pointer: coarse)").matches;
  const memoria = (navigator as NavegadorComMemoria).deviceMemory;
  if (grosso && typeof memoria === "number" && memoria < 4) return false;
  // Probe barato de WebGL 1 (contexto descartado em seguida). Sem WebGL →
  // fica a aurora estática, sem custo algum.
  const sonda = document.createElement("canvas");
  const gl = sonda.getContext("webgl");
  if (!gl) return false;
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  return true;
}

type Fase = "aguardando" | "ativo" | "desligado";

export function CampoBrasa() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [fase, setFase] = useState<Fase>("aguardando");

  // Fase 1 — gates no idle (nunca no caminho crítico da hidratação).
  useEffect(() => {
    if (fase !== "aguardando") return;
    let vivo = true;
    const cancelar = agendarOcioso(() => {
      if (!vivo) return;
      setFase(passaNosGates() ? "ativo" : "desligado");
    }, 800);
    return () => {
      vivo = false;
      cancelar();
    };
  }, [fase]);

  // Fase 2 — chunk dinâmico + montagem do motor; desmonte limpo em
  // contextlost, falha de import/contexto ou reduce ligado ao vivo.
  useEffect(() => {
    if (fase !== "ativo") return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    let vivo = true;
    let desmontarMotor: (() => void) | null = null;

    const mqlReduce = window.matchMedia(MQ_REDUCE);
    const aoMudarReduce = () => {
      if (mqlReduce.matches) setFase("desligado");
    };
    mqlReduce.addEventListener("change", aoMudarReduce);

    void import("./campoBrasa.frag")
      .then((motor) => {
        if (!vivo) return;
        desmontarMotor = motor.montarCampoBrasa(canvas, {
          aoPerderContexto: () => {
            if (vivo) setFase("desligado");
          },
        });
        if (!desmontarMotor && vivo) setFase("desligado");
      })
      .catch(() => {
        if (vivo) setFase("desligado");
      });

    return () => {
      vivo = false;
      mqlReduce.removeEventListener("change", aoMudarReduce);
      desmontarMotor?.();
    };
  }, [fase]);

  if (fase !== "ativo") return null;
  return <canvas ref={canvasRef} aria-hidden className="campo-brasa" />;
}
