/**
 * campoBrasa.frag.ts — shader + motor WebGL 1 PURO da "Câmara de Brasa"
 * (missão MATÉRIA VIVA, plano §3 crit.1/crit.6 + emendas R6/R12c — Onda 1A).
 *
 * Este módulo é o CHUNK ADIADO do campo: só chega via `import()` dinâmico do
 * gate `CampoBrasa.tsx` (quem reprova nos gates nem o baixa — R12b). Zero
 * dependência (sem ogl/three): 1 fullscreen triangle + 1 fragment shader com
 * fbm de 3 oitavas (névoa de tinta advectada) e 2 grades de brasas
 * procedurais. CSP intocada: WebGL/canvas não são governados por style-src;
 * as strings de shader são literais do bundle (script-src 'self' + nonce +
 * strict-dynamic cobre); nenhuma escrita de estilo em lugar algum.
 *
 * R6 (LEI — WCAG 2.2.2, DECISÃO "o campo se ASSENTA"): a fase de ABERTURA
 * dura ≤5s (`DURACAO_ABERTURA` = 4s, com desaceleração quadrática até zero).
 * Depois disso o campo ASSENTA: nada avança sozinho — o "tempo" do campo
 * (`tempoCampo`, que move névoa, subida e cintilar das brasas) só anda
 * empurrado por CURSOR (delta do lerp) e SCROLL (delta do progresso).
 * Movimento dirigido pelo usuário é isento do 2.2.2 — sem botão de pausa
 * extra por decisão registrada no plano (§12 R6). Quando assentado e sem
 * interação, o rAF é DESLIGADO (zero draw, zero CPU/GPU) e reacorda por
 * pointermove/scroll/resize/tema.
 *
 * Perf (gate ≤1.8ms/frame): dpr ≤1.5 (1 em pointer:coarse), 3 oitavas fixas,
 * 2 grades de brasas, powerPreference "low-power",
 * failIfMajorPerformanceCaveat (rasterização por software não monta — o
 * fallback é a aurora CSS), pausa por IntersectionObserver e
 * visibilitychange, rects cacheados no resize (zero layout read em handler
 * de move), uniforms dinâmicos = 3 floats/quadro.
 *
 * COR (crit.7 — verde/jade BANIDO): as duas cores vêm SÓ dos tokens
 * `--luz-tinta` e `--brasa-ember` lidos via getComputedStyle — nunca
 * hardcoded no frag — e são RE-LIDAS na troca de tema do SO (R12c). No
 * shader elas NUNCA se interpolam por matiz: a composição é src-over
 * ponderado em RGB (caminho por luminância/dessaturação); como ambos os
 * tokens têm canal G baixo/médio dominado por R ou B nos dois temas, nenhum
 * pixel intermediário pode cair na faixa proibida 70–200° (QA da Onda 3
 * reprova por readPixels).
 *
 * TRAVA M3 (Bazley): `uMask` capa o alfa composto sob a coluna de texto em
 * 0.05 (claro) / 0.06 (escuro) — brasa jamais banha número/citação; os chips
 * `bg-realce` opacos seguem por cima da camada de qualquer forma.
 */

type OpcoesCampo = {
  /** Chamado em `webglcontextlost` ou falha irrecuperável — o gate desmonta o canvas. */
  aoPerderContexto?: () => void;
};

const DURACAO_ABERTURA = 4; // s — teto duro de movimento autônomo (R6: ≤5s)

const VERT = `
attribute vec2 aPos;
void main() {
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`;

const FRAG = `
precision mediump float;

uniform vec2 uResolucao;
uniform float uTempo;   /* tempo do CAMPO — dirigido (abertura + interação) */
uniform vec2 uMouse;    /* uv 0..1 (origem embaixo), já lerpado no JS */
uniform float uScroll;  /* progresso de saída do hero, 0..~1.2 */
uniform vec4 uMask;     /* rect uv (x0, y0, x1, y1) da coluna de texto */
uniform float uMaskCap; /* teto de alfa sob a máscara: 0.05 claro / 0.06 escuro */
uniform vec3 uCorTinta; /* --luz-tinta (getComputedStyle, R12c) */
uniform vec3 uCorBrasa; /* --brasa-ember (getComputedStyle, R12c) */
uniform float uTema;    /* 0 claro / 1 escuro */

float hash21(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float ruido(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

/* fbm de 3 oitavas FIXAS (orçamento de frame) */
float fbm3(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 3; i++) {
    v += amp * ruido(p);
    p = p * 2.03 + vec2(11.31, 7.79);
    amp *= 0.5;
  }
  return v;
}

/* Grade de brasas procedurais: 1 fagulha por célula (~28% das células),
   subindo e cintilando com o TEMPO DO CAMPO — quando o campo assenta (R6),
   uTempo para de andar sozinho e as brasas congelam até o usuário mexer. */
float brasas(vec2 p, float n, float vel, float semente, float raio) {
  vec2 g = p * n;
  g.y -= uTempo * vel;
  vec2 cel = floor(g);
  vec2 f = fract(g);
  float r1 = hash21(cel + semente);
  float r2 = hash21(cel + semente + 17.0);
  float r3 = hash21(cel + semente + 31.0);
  vec2 pos = vec2(0.2 + 0.6 * r2, 0.2 + 0.6 * r3);
  /* edges crescentes SEMPRE (smoothstep com edge0>=edge1 é indefinido) */
  float s = 1.0 - smoothstep(0.0, raio, length(f - pos));
  s *= 0.55 + 0.45 * sin(uTempo * (1.5 + 3.0 * r1) + r1 * 6.2831);
  return s * step(0.72, r1);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolucao;
  vec2 p = vec2(uv.x * (uResolucao.x / max(uResolucao.y, 1.0)), uv.y);

  /* recuo do campo ao sair do hero (volta ao subir) — plano crit.1 */
  float recuo = clamp(1.0 - uScroll * 1.2, 0.0, 1.0);

  /* clareira inercial sob o cursor (uMouse já chega com lerp 0.06) */
  float longe = smoothstep(0.0, 1.0, distance(uv, uMouse) / 0.34);
  float clareira = mix(0.35, 1.0, longe);

  /* névoa de tinta-safira: fbm advectado + parallax leve de scroll */
  vec2 deriva = vec2(uTempo * 0.02, uTempo * 0.05 + uScroll * 0.22);
  float nevoa = fbm3(p * 2.4 + deriva + (uMouse - 0.5) * 0.25);
  nevoa = smoothstep(0.38, 0.92, nevoa);
  float aTinta = nevoa * mix(0.075, 0.095, uTema) * clareira * recuo;

  /* duas grades de brasas (escalas/velocidades distintas) subindo do rodapé */
  float e1 = brasas(p, 8.0, 0.06, 3.0, 0.16);
  float e2 = brasas(p, 15.0, 0.1, 27.0, 0.11);
  float sobe = 1.0 - smoothstep(0.1, 1.05, uv.y);
  float aBrasa = (e1 * 0.5 + e2 * 0.38) * sobe * clareira * recuo;

  /* composição src-over (brasa sobre tinta) — média ponderada em RGB, nunca
     hue-lerp: o caminho intermediário dessatura (canal G nunca domina) */
  float alfa = aBrasa + aTinta * (1.0 - aBrasa);
  vec3 cor = (uCorBrasa * aBrasa + uCorTinta * aTinta * (1.0 - aBrasa)) /
    max(alfa, 0.0001);

  /* trava M3: cap de alfa sob a coluna de texto (uMask em uv) */
  float dentro = step(uMask.x, uv.x) * step(uv.x, uMask.z) *
    step(uMask.y, uv.y) * step(uv.y, uMask.w);
  alfa = mix(alfa, min(alfa, uMaskCap), dentro);

  /* saída premultiplicada (contexto com premultipliedAlpha: true) */
  gl_FragColor = vec4(cor * alfa, alfa);
}
`;

/** Lê um triplet RGB space-separated ("42 54 84") de um token e normaliza 0..1. */
function lerTriplet(
  estilo: CSSStyleDeclaration,
  nome: string,
  reserva: readonly [number, number, number],
): [number, number, number] {
  const partes = estilo.getPropertyValue(nome).trim().split(/\s+/).map(Number);
  if (partes.length === 3 && partes.every((n) => Number.isFinite(n))) {
    return [partes[0] / 255, partes[1] / 255, partes[2] / 255];
  }
  return [reserva[0] / 255, reserva[1] / 255, reserva[2] / 255];
}

/**
 * Monta o campo no `canvas` (que DEVE estar dentro do container que define a
 * geometria — o hero `.tem-foco`). Devolve a função de desmonte (idempotente)
 * ou `null` se o contexto/shader não puder ser criado (o gate então desliga
 * e o fundo fica com a aurora CSS).
 */
export function montarCampoBrasa(
  canvas: HTMLCanvasElement,
  { aoPerderContexto }: OpcoesCampo = {},
): (() => void) | null {
  const paiDoCanvas = canvas.parentElement;
  if (!paiDoCanvas) return null;
  // Alias já estreitado (non-null) para as closures abaixo.
  const container: HTMLElement = paiDoCanvas;

  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: true,
    preserveDrawingBuffer: false,
    powerPreference: "low-power",
    // GPU por software não paga o frame — melhor a aurora estática.
    failIfMajorPerformanceCaveat: true,
  });
  if (!gl) return null;

  // ---- programa -----------------------------------------------------------
  function compilar(tipo: number, fonte: string): WebGLShader | null {
    if (!gl) return null;
    const shader = gl.createShader(tipo);
    if (!shader) return null;
    gl.shaderSource(shader, fonte);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  const vert = compilar(gl.VERTEX_SHADER, VERT);
  const frag = compilar(gl.FRAGMENT_SHADER, FRAG);
  const programa = gl.createProgram();
  // Falha em qualquer etapa: liberar TUDO que já foi criado e devolver o
  // contexto (loseContext) — sem isso um frag inválido vazaria vert+contexto
  // vivos até o GC (auditoria 2026-07-13, achado 10).
  const abortar = () => {
    if (vert) gl.deleteShader(vert);
    if (frag) gl.deleteShader(frag);
    if (programa) gl.deleteProgram(programa);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return null;
  };
  if (!vert || !frag || !programa) return abortar();
  gl.attachShader(programa, vert);
  gl.attachShader(programa, frag);
  gl.linkProgram(programa);
  if (!gl.getProgramParameter(programa, gl.LINK_STATUS)) {
    return abortar();
  }
  gl.useProgram(programa);

  // Fullscreen triangle (3 vértices cobrem o viewport; WebGL 1 não tem
  // gl_VertexID, então o triângulo vai num buffer mínimo).
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 3, -1, -1, 3]),
    gl.STATIC_DRAW,
  );
  const aPos = gl.getAttribLocation(programa, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  const uResolucao = gl.getUniformLocation(programa, "uResolucao");
  const uTempo = gl.getUniformLocation(programa, "uTempo");
  const uMouse = gl.getUniformLocation(programa, "uMouse");
  const uScroll = gl.getUniformLocation(programa, "uScroll");
  const uMask = gl.getUniformLocation(programa, "uMask");
  const uMaskCap = gl.getUniformLocation(programa, "uMaskCap");
  const uCorTinta = gl.getUniformLocation(programa, "uCorTinta");
  const uCorBrasa = gl.getUniformLocation(programa, "uCorBrasa");
  const uTema = gl.getUniformLocation(programa, "uTema");

  // ---- estado -------------------------------------------------------------
  let destruido = false;
  let rodando = false;
  let visivel = true;
  let abaVisivel = !document.hidden;
  let idQuadro = 0;
  let ultimoTs: number | null = null;

  // R6: relógio da abertura (para de existir após DURACAO_ABERTURA) e tempo
  // DIRIGIDO do campo (só anda com abertura/cursor/scroll).
  let relogioAbertura = 0;
  let tempoCampo = 0;

  const mouseAlvo = { x: 0.5, y: 0.55 };
  const mouse = { x: 0.5, y: 0.55 };
  let scrollAlvo = 0;
  let scrollAtual = 0;

  // Geometria cacheada no resize (zero layout read em pointermove/scroll).
  let topoHeroDoc = 0; // topo do container em coordenadas de documento
  let esquerdaHeroDoc = 0;
  let alturaHero = 1;
  let larguraHero = 1;

  // ---- tokens de cor (R12c: re-lidos na troca de tema do SO) ---------------
  const mqlEscuro = window.matchMedia("(prefers-color-scheme: dark)");
  function aplicarTema() {
    const estilo = getComputedStyle(document.documentElement);
    const tinta = lerTriplet(estilo, "--luz-tinta", [42, 54, 84]);
    const brasa = lerTriplet(estilo, "--brasa-ember", [160, 58, 6]);
    const escuro = mqlEscuro.matches;
    if (!gl) return;
    gl.uniform3f(uCorTinta, tinta[0], tinta[1], tinta[2]);
    gl.uniform3f(uCorBrasa, brasa[0], brasa[1], brasa[2]);
    gl.uniform1f(uTema, escuro ? 1 : 0);
    gl.uniform1f(uMaskCap, escuro ? 0.06 : 0.05); // trava M3
    acordar();
  }

  // ---- geometria / máscara --------------------------------------------------
  function medir() {
    if (!gl) return;
    const rc = container.getBoundingClientRect();
    const dpr = Math.min(
      window.devicePixelRatio || 1,
      window.matchMedia("(pointer: coarse)").matches ? 1 : 1.5,
    );
    const w = Math.max(1, Math.round(rc.width * dpr));
    const h = Math.max(1, Math.round(rc.height * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
    gl.uniform2f(uResolucao, w, h);

    topoHeroDoc = rc.top + window.scrollY;
    esquerdaHeroDoc = rc.left + window.scrollX;
    alturaHero = Math.max(rc.height, 1);
    larguraHero = Math.max(rc.width, 1);

    // Máscara da coluna de texto (uv, origem embaixo). HORIZONTE crit.2
    // (Onda 1D, re-medição do uMask/E1): a composição da capa deixou de ser
    // um bloco centrado único — vira uma referência DEDICADA e invisível,
    // `.capa-mascara` (cinema/hero.css §8), medida aqui do mesmo jeito de
    // sempre (getBoundingClientRect do alvo `[data-mascara-brasa]` — zero
    // mudança de motor, só troca QUEM está marcado). Ela cobre a faixa da
    // coluna de texto esquerda (manchete/linha-fina/CTAs + a orelha
    // esquerda/vinco, que caem dentro da mesma faixa vertical) do topo ao
    // fim do rolo da capa; a orelha DIREITA (metadado não-crítico) fica
    // fora, no lado onde o campo é livre por design (ver relatório da
    // Onda 1D/CAPA — sinalizado para a re-enumeração AA da Onda 4, D39).
    // Sem a marca (defesa em profundidade — nunca deveria faltar, a Onda 2
    // sempre a inclui): fallback aproxima a faixa esquerda nova (~60% —
    // mais estreita que os 68% do layout centrado anterior, já que a capa
    // ancora a manchete a partir de `palco-inicio`, não do centro do hero).
    const alvo = container.querySelector("[data-mascara-brasa]");
    if (alvo) {
      const rm = alvo.getBoundingClientRect();
      const x0 = Math.max(0, (rm.left - rc.left) / rc.width);
      const x1 = Math.min(1, (rm.right - rc.left) / rc.width);
      const y0 = Math.max(0, 1 - (rm.bottom - rc.top) / rc.height);
      const y1 = Math.min(1, 1 - (rm.top - rc.top) / rc.height);
      gl.uniform4f(uMask, x0, y0, x1, y1);
    } else {
      gl.uniform4f(uMask, 0, 0, 0.6, 1);
    }
    acordar();
  }

  // ---- laço dirigido (render-on-demand) ------------------------------------
  function desenhar() {
    if (!gl) return;
    gl.uniform1f(uTempo, tempoCampo);
    gl.uniform2f(uMouse, mouse.x, mouse.y);
    gl.uniform1f(uScroll, scrollAtual);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function quadro(ts: number) {
    idQuadro = 0;
    if (destruido) return;
    const dt =
      ultimoTs === null ? 1 / 60 : Math.min((ts - ultimoTs) / 1000, 1 / 20);
    ultimoTs = ts;

    let mexeu = false;

    // R6 — abertura ≤5s com desaceleração quadrática até ZERO autônomo.
    if (relogioAbertura < DURACAO_ABERTURA) {
      relogioAbertura += dt;
      const t = Math.min(relogioAbertura / DURACAO_ABERTURA, 1);
      tempoCampo += dt * (1 - t * t);
      mexeu = true;
    }

    // Cursor: lerp 0.06/frame; o DESLOCAMENTO do lerp é o que empurra o
    // tempo do campo depois de assentado ("clareira inercial").
    const dx = mouseAlvo.x - mouse.x;
    const dy = mouseAlvo.y - mouse.y;
    const dist = Math.hypot(dx, dy);
    if (dist > 0.0005) {
      mouse.x += dx * 0.06;
      mouse.y += dy * 0.06;
      tempoCampo += Math.min(dist * 0.06 * 2.0, dt * 3);
      mexeu = true;
    } else {
      mouse.x = mouseAlvo.x;
      mouse.y = mouseAlvo.y;
    }

    // Scroll: segue com inércia leve própria; o delta também empurra o campo.
    const ds = scrollAlvo - scrollAtual;
    if (Math.abs(ds) > 0.0008) {
      scrollAtual += ds * 0.12;
      tempoCampo += Math.min(Math.abs(ds) * 0.12 * 2.5, dt * 3);
      mexeu = true;
    } else {
      scrollAtual = scrollAlvo;
    }

    desenhar();

    if (mexeu && visivel && abaVisivel) {
      idQuadro = window.requestAnimationFrame(quadro);
    } else {
      // ASSENTADO (R6): zero draw até a próxima interação real.
      rodando = false;
      ultimoTs = null;
    }
  }

  function acordar() {
    if (destruido || rodando || !visivel || !abaVisivel) return;
    rodando = true;
    ultimoTs = null;
    idQuadro = window.requestAnimationFrame(quadro);
  }

  // ---- entradas (passivas, sem layout read) ---------------------------------
  function aoMover(ev: PointerEvent) {
    if (ev.pointerType === "touch") return; // touch fala via scroll
    // Geometria a partir do cache do resize (viewport → documento → uv);
    // ler scrollX/scrollY não força reflow (zero layout read no handler).
    const xDoc = ev.clientX + window.scrollX - esquerdaHeroDoc;
    const yDoc = ev.clientY + window.scrollY - topoHeroDoc;
    mouseAlvo.x = Math.min(Math.max(xDoc / larguraHero, 0), 1);
    mouseAlvo.y = Math.min(Math.max(1 - yDoc / alturaHero, 0), 1);
    acordar();
  }

  function aoRolar() {
    scrollAlvo = Math.min(Math.max(window.scrollY / alturaHero, 0), 1.2);
    acordar();
  }

  function aoMudarVisibilidade() {
    abaVisivel = !document.hidden;
    acordar();
  }

  const io = new IntersectionObserver(
    (entradas) => {
      visivel = entradas.some((e) => e.isIntersecting);
      acordar();
    },
    { threshold: 0 },
  );

  const ro = new ResizeObserver(() => medir());

  function aoPerderContextoInterno() {
    // "contextlost → desmonta limpo": sem restore; o gate remove o canvas e
    // o fundo volta à aurora CSS. (Não chamamos preventDefault de propósito.)
    destruir();
    aoPerderContexto?.();
  }

  container.addEventListener("pointermove", aoMover, { passive: true });
  window.addEventListener("scroll", aoRolar, { passive: true });
  document.addEventListener("visibilitychange", aoMudarVisibilidade);
  canvas.addEventListener("webglcontextlost", aoPerderContextoInterno);
  mqlEscuro.addEventListener("change", aplicarTema);
  io.observe(container);
  ro.observe(container);

  // Primeiro quadro: mede, aplica cores do tema atual e liga a abertura.
  medir();
  aplicarTema();
  aoRolar();
  acordar();

  function destruir() {
    if (destruido) return;
    destruido = true;
    window.cancelAnimationFrame(idQuadro);
    container.removeEventListener("pointermove", aoMover);
    window.removeEventListener("scroll", aoRolar);
    document.removeEventListener("visibilitychange", aoMudarVisibilidade);
    canvas.removeEventListener("webglcontextlost", aoPerderContextoInterno);
    mqlEscuro.removeEventListener("change", aplicarTema);
    io.disconnect();
    ro.disconnect();
    if (gl && !gl.isContextLost()) {
      gl.deleteBuffer(buffer);
      gl.deleteProgram(programa);
      gl.deleteShader(vert);
      gl.deleteShader(frag);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    }
  }

  return destruir;
}
