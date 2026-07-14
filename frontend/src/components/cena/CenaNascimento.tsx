/**
 * CenaNascimento — a cena "Da mina à vitrine" (D15/D16/D17/D18/E12, §5c da
 * direção). Server Component, SVG inline: ZERO JS necessário para o
 * diagrama existir e fazer sentido sozinho (D16 — "estado final = default
 * do CSS"). O motion (scrub GSAP) é uma camada OPCIONAL por cima, montada
 * por `NascimentoScrub.tsx` (client, ilha separada) — este arquivo nunca
 * importa gsap, nunca é "use client".
 *
 * STORYBOARD (6 planos, `data-plano="1".."6"`, §5c da direção):
 *   1 mina        — 6 selos de fonte batem (E12: B3 + CVM · SEC · BCB ·
 *                    WORLD BANK · STN — o 6º selo, B3, é a fonte REAL do
 *                    dado desta cena).
 *   2 extração    — do selo B3 se desprende a pedra bruta com o dado REAL
 *                    (D17: 1º item de `exemplosProntos()`/
 *                    `DATA_CARTEIRA_IBOV` — zero número inventado).
 *   3 lapidação   — 5 facetas D1..D5 dobram sobre a pedra (path-morph
 *                    PROIBIDO: as facetas são 5 formas ESTÁTICAS/rígidas —
 *                    "camadas de opacity", nunca `d` redesenhado).
 *   4 gate        — aro fecha; uma 2ª pedra SEM selo é desviada à bandeja
 *                    "sem fonte → lacuna declarada" (par aviso, nunca erro).
 *   5 carimbo     — punção `[1]` crava; a citação completa imprime.
 *   6 engaste     — a gema pousa no mini-chip; o fio sai da cena (handoff
 *                    para `FioDaFonte`/as gemas reais da página).
 *
 * D16 (regra de resiliência, LEI): todo grupo nasce com opacity:1/transform
 * padrão em `cinema/lapidacao.css` — o SVG abaixo É o estado FINAL completo
 * (todos os planos simultaneamente visíveis, como um diagrama técnico
 * "explodido"). `NascimentoScrub` aplica `fromTo` por cima (estado inicial
 * ESCONDIDO só existe depois que o JS monta, no cliente) — sem JS, sob
 * `prefers-reduced-motion: reduce`, ou antes do chunk carregar, o visitante
 * vê o diagrama pronto, nunca uma tela vazia.
 *
 * A11Y (D18): `<figure role="img" aria-label>` some a árvore inteira do SVG
 * como uma única imagem para tecnologia assistiva (o `<svg aria-hidden>`
 * dentro reforça isso); AO LADO — como conteúdo real, não dentro da região
 * tratada como imagem — h3 `sr-only` + `<ol>` com as 6 legendas legíveis em
 * ordem (o leitor de tela recebe o passo a passo estruturado). Reusável
 * ESTÁTICA em /como-funciona (a raia 3C importa este mesmo componente,
 * envolvida por `view-timeline` nomeada em vez do GSAP — mesmo SVG, motor
 * de scrub diferente).
 */

import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

/** E12: seis selos — os 5 das dimensões + B3 (a fonte REAL do dado da cena). */
const SELOS = ["B3", "CVM", "SEC", "BCB", "WORLD BANK", "STN"] as const;

/** D1..D5 — mesmos rótulos de `page.tsx` (DIMENSOES), abreviados para o mono da cena. */
const FACETAS = [
  { numero: "D1", rotulo: "FUNDAMENTOS" },
  { numero: "D2", rotulo: "PARES GLOBAIS" },
  { numero: "D3", rotulo: "MACRO BRASIL" },
  { numero: "D4", rotulo: "MACRO GLOBAL" },
  { numero: "D5", rotulo: "ELOS" },
] as const;

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function formatPct(pct: number): string {
  return pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

/** Arredonda para 0.1 — geometria estática, só por legibilidade do `d`. */
function r(n: number): number {
  return Math.round(n * 10) / 10;
}

/**
 * 5 facetas em rosa dos ventos ao redor de (cx, cy): cada uma é um kite
 * ESTÁTICO (ponta externa em raio R, duas bases em raio interno, e o centro
 * comum) — 5 formas rígidas que dão o efeito de corte, sem NUNCA morphar
 * `d` (D18: path-morph PROIBIDO). Calculado 1x em módulo (não em request:
 * é geometria fixa, zero custo).
 */
function facetasPath(cx: number, cy: number, raioExterno: number, raioInterno: number) {
  const pontos = (raioDeg: number) => {
    const rad = (raioDeg * Math.PI) / 180;
    return { x: cx + raioExterno * Math.cos(rad), y: cy + raioExterno * Math.sin(rad) };
  };
  const base = (raioDeg: number) => {
    const rad = (raioDeg * Math.PI) / 180;
    return { x: cx + raioInterno * Math.cos(rad), y: cy + raioInterno * Math.sin(rad) };
  };
  const angulos = [-90, -18, 54, 126, 198];
  return angulos.map((ang, i) => {
    const tip = pontos(ang);
    const esq = base(ang - 36);
    const dir = base(ang + 36);
    const d = `M ${r(tip.x)} ${r(tip.y)} L ${r(dir.x)} ${r(dir.y)} L ${cx} ${cy} L ${r(esq.x)} ${r(esq.y)} Z`;
    // Posição do rótulo: um pouco além da ponta, na mesma direção radial.
    const rad = (ang * Math.PI) / 180;
    const rotuloX = cx + (raioExterno + 14) * Math.cos(rad);
    const rotuloY = cy + (raioExterno + 14) * Math.sin(rad);
    const anchor: "start" | "middle" | "end" =
      Math.cos(rad) > 0.35 ? "start" : Math.cos(rad) < -0.35 ? "end" : "middle";
    return { d, i, rotuloX: r(rotuloX), rotuloY: r(rotuloY), anchor };
  });
}

type PropsCenaNascimento = {
  className?: string;
};

export function CenaNascimento({ className }: PropsCenaNascimento) {
  const papel = exemplosProntos()[0];
  const dado = `${papel.ticker} · ${formatPct(papel.participacaoPct)}% do IBOV`;
  const dataFmt = formatDataIso(DATA_CARTEIRA_IBOV);
  // Mesma anatomia de citação já aprovada em #prova/hero (D37: zero copy
  // nova nesta raia — reusa literalmente "Fonte: B3 · Carteira teórica do
  // Ibovespa · {data}"; aqui vira o carimbo "[1] ...").
  const citacao = `[1] B3 · Carteira teórica do Ibovespa · ${dataFmt}`;

  const cxGema = 460;
  const cyGema = 340;
  const facetas = facetasPath(cxGema, cyGema, 72, 34);

  // Selos: 6 centros distribuídos na moldura da mina; índice 0 = B3 (E12).
  const selosX = [100, 244, 388, 532, 676, 820];
  const selCyBase = 92;

  return (
    <figure
      role="img"
      aria-label="Diagrama: como um número público entra na tese, das fontes oficiais até a citação carimbada."
      className={className ? `nascimento-figura ${className}` : "nascimento-figura"}
    >
      <h3 className="sr-only">Como um número nasce na tese, em seis passos</h3>

      <svg
        viewBox="0 0 920 690"
        className="nascimento-svg"
        aria-hidden="true"
        focusable="false"
      >
        {/* Espinha central — conecta os 6 planos, sempre visível (decorativo). */}
        <line x1={cxGema} y1={130} x2={cxGema} y2={628} className="nascimento-esteira" />

        {/* PLANO 1 — a mina: moldura + 6 selos (E12: B3 é o índice 0). */}
        <g data-plano="1" className="nascimento-plano nascimento-plano--mina">
          <rect x={20} y={20} width={880} height={110} rx={4} className="nascimento-moldura" />
          <text x={460} y={40} textAnchor="middle" className="nascimento-rotulo-secao">
            FONTES OFICIAIS
          </text>
          {SELOS.map((selo, i) => (
            <g
              key={selo}
              data-selo={selo}
              className={
                i === 0
                  ? "nascimento-selo nascimento-selo--fonte"
                  : "nascimento-selo"
              }
            >
              <circle cx={selosX[i]} cy={selCyBase} r={24} />
              <text x={selosX[i]} y={selCyBase + 40} textAnchor="middle" className="nascimento-selo-texto">
                {selo}
              </text>
            </g>
          ))}
          {/* Linha de extração — sai do selo B3 (índice 0) rumo à pedra bruta. */}
          <path
            d={`M ${selosX[0]} ${selCyBase + 24} C ${selosX[0]} ${selCyBase + 70}, 380 130, 440 150`}
            className="nascimento-linha-extracao"
          />
        </g>

        {/* PLANO 2 — extração: pedra bruta com o dado REAL (D17). */}
        <g data-plano="2" className="nascimento-plano nascimento-plano--extracao">
          <path
            d="M 420 150 L 470 143 L 508 168 L 497 208 L 438 212 L 413 183 Z"
            className="nascimento-pedra-bruta"
          />
          <text x={460} y={230} textAnchor="middle" className="nascimento-dado">
            {dado}
          </text>
        </g>

        {/* PLANO 3 — lapidação: 5 facetas D1..D5 (camadas de opacity, D18). */}
        <g data-plano="3" className="nascimento-plano nascimento-plano--facetas">
          {facetas.map((f, i) => (
            <g key={FACETAS[i].numero} className={`nascimento-faceta nascimento-faceta--${i + 1}`}>
              <path d={f.d} />
              <text x={f.rotuloX} y={f.rotuloY} textAnchor={f.anchor} className="nascimento-faceta-rotulo">
                {FACETAS[i].numero} {FACETAS[i].rotulo}
              </text>
            </g>
          ))}
        </g>

        {/* PLANO 4 — o gate: aro fecha; 2ª pedra sem selo vai à bandeja. */}
        <g data-plano="4" className="nascimento-plano nascimento-plano--gate">
          <circle cx={330} cy={470} r={38} className="nascimento-aro" />
          <text x={390} y={464} className="nascimento-legenda-mono">
            fonte · B3
          </text>
          <text x={390} y={482} className="nascimento-legenda-mono">
            data · {dataFmt}
          </text>
          <g className="nascimento-bandeja">
            <rect x={590} y={440} width={130} height={62} rx={6} />
            <path d="M 622 458 L 648 452 L 668 466 L 660 484 L 630 486 L 616 470 Z" className="nascimento-pedra-lacuna" />
            <text x={655} y={520} textAnchor="middle" className="nascimento-legenda-mono">
              sem fonte → lacuna declarada
            </text>
          </g>
        </g>

        {/* PLANO 5 — o carimbo: punção crava, citação completa imprime. */}
        <g data-plano="5" className="nascimento-plano nascimento-plano--carimbo">
          <rect x={444} y={550} width={32} height={16} rx={2} className="nascimento-puncao" />
          <text x={460} y={608} textAnchor="middle" className="nascimento-citacao">
            {citacao}
          </text>
        </g>

        {/* PLANO 6 — o engaste: gema pousa no mini-chip; fio sai da cena. */}
        <g data-plano="6" className="nascimento-plano nascimento-plano--engaste">
          <g className="nascimento-mini-chip">
            <rect x={410} y={630} width={100} height={44} rx={4} className="nascimento-mini-chip-fundo" />
            <path d="M 410 630 L 480 630 M 410 630 L 410 674" className="nascimento-mini-chip-aresta" />
            <path d="M 510 630 L 440 674 M 510 674 L 510 630" className="nascimento-mini-chip-quilha" />
          </g>
          <circle cx={460} cy={652} r={13} className="nascimento-gema-final" />
          <path
            d="M 460 674 L 460 682"
            pathLength={1}
            className="nascimento-fio-saida"
            data-fio-saida=""
          />
        </g>
      </svg>

      {/* As 6 legendas (D18) — copy VERBATIM de
          `.maestro/ondas/copy-horizonte-spec.md` §2.3, aplicada pelo integrador
          da Onda 2. A redação anterior (pré-spec) descrevia a cena com o
          vocabulário da joalheria ("a mina", "lapidação", "a gema pousa") e
          estourava sozinha o ORÇAMENTO DA METÁFORA (§11 do spec: teto de 3
          toques no site inteiro, e nenhum deles aqui) — sr-only é texto
          visível para leitor de tela e conta no grep do gate. Números:
          interpolados de `exemplosProntos()`/`DATA_CARTEIRA_IBOV`, nunca
          literais; legenda 2 e legenda 5 citam a MESMA fonte (B3) e a MESMA
          data (E12/E28). */}
      <ol className="sr-only">
        <li>
          As fontes oficiais entram primeiro: B3, CVM, SEC, Banco Central, Banco Mundial e
          Tesouro Nacional.
        </li>
        <li>
          Da B3 se desprende o dado cru: {dado}, do jeito que o índice foi publicado em{" "}
          {dataFmt}.
        </li>
        <li>
          Cinco dimensões cortam o mesmo dado: fundamentos, pares globais, macro do Brasil,
          macro global e elos causais.
        </li>
        <li>
          Nada passa sem fonte e data: o que não está na fonte pública vira lacuna declarada,
          nunca vira número estimado.
        </li>
        <li>A citação é cravada no texto: {citacao}.</li>
        <li>
          O número entra na tese pronto para ser conferido — e a fonte fica registrada no fim
          do documento, com data.
        </li>
      </ol>
    </figure>
  );
}
