/**
 * CenaNascimento — a cena do nascimento do número (D15/D16/D17/D18/E12;
 * ESTENDIDA a 8 planos pela missão OURIVESARIA, raia 1C — §3-C3/§7-B1/B5).
 * Server Component, SVG inline: ZERO JS necessário para o diagrama existir
 * e fazer sentido sozinho (D16 — "estado final = default do CSS"). O motion
 * (scrub GSAP) é uma camada OPCIONAL por cima, montada por
 * `NascimentoScrub.tsx` (client, ilha separada) — este arquivo nunca
 * importa gsap, nunca é "use client" (lei das ilhas: a ilha RECEBE este
 * markup como children, não o renderiza).
 *
 * STORYBOARD (8 planos, `data-plano="1".."8"`, §7-B5 — split do antigo
 * plano 4 em conferência + contraprova, e plano 8 novo de trilha):
 *   1 fontes       — 6 selos oficiais batem (E12: B3 é a fonte REAL).
 *   2 extração     — do selo B3 se desprende a pedra bruta com o dado REAL
 *                    (D17: 1º item de `exemplosProntos()`/DATA_CARTEIRA_IBOV).
 *   3 lapidação    — 5 facetas D1..D5 (formas RÍGIDAS; path-morph PROIBIDO).
 *   4 conferência  — o aro fecha sobre as duas provas: fonte · data.
 *   5 contraprova  — a 2ª pedra SEM selo é desviada à bandeja "sem fonte →
 *                    lacuna declarada" (par aviso, nunca erro).
 *   6 carimbo      — punção `[1]` crava; a citação completa imprime.
 *   7 engaste      — a gema pousa no mini-chip.
 *   8 trilha       — o caminho fica REGISTRADO (traço pontilhado de retorno
 *                    até o selo B3 — refazível de trás para frente) e o fio
 *                    de saída se DESENHA até y=686 (handoff para a página).
 *
 * D16 (regra de resiliência, LEI): todo grupo nasce visível — o SVG abaixo
 * É o estado FINAL completo. `NascimentoScrub` aplica `fromTo` por cima
 * (estado inicial ESCONDIDO só existe depois que o JS monta, no cliente).
 *
 * A11Y (§7-B1, achados 2/21/22): o `<figure role="img" aria-label>` contém
 * SÓ o diagrama (descendentes de role=img são apresentacionais para AT);
 * o h3 sr-only e o `<ol>` com as 8 legendas vivem FORA do figure, como
 * irmãos — FONTE ÚNICA (E-A3): uma redação, duas superfícies. A prop
 * `legendasVisiveis` decide a superfície: true na landing (o `<ol>` é o
 * letreiro visível, estilizado por cinema/nascimento.css); default false
 * (sr-only — /como-funciona segue lendo as mesmas 8 legendas sem exibi-las).
 * Copy das legendas: TRANSCRIÇÃO BYTE-FIEL de .maestro/copy-ourivesaria.md
 * §1 (E5 — divergência sobe ao maestro; números SEMPRE interpolados).
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

/**
 * ESPINHA CENTRAL (x = cxGema) — R1/V2, missão ARREMATE (ruling R15).
 * Era UMA <line> sólida y=130→628 que atravessava o INTERIOR da pedra
 * bruta (fill-opacity .22), do texto do dado, das facetas (.16–.28), do
 * texto "data · {data}" do plano 4 e do texto da citação. A regra de
 * ferro global proíbe conectora cruzando caixa/placa/texto em QUALQUER
 * rota — e esta cena roda em duas (`/` e `/como-funciona`), sendo que na
 * interna ela fica PERMANENTEMENTE no estado final (sem scrub), então a
 * travessia era visível 100% do tempo lá.
 *
 * A espinha CONTINUA existindo: sobraram os 5 trechos que já corriam em
 * corredor vazio — é exatamente o que a linha pareceria se todos os
 * atores fossem opacos (a oclusão que a translucidez quebrava). Folga
 * mínima medida: 2,25px contra a caixa PINTADA de cada ator (inclui meio
 * stroke), padrão FOLGA_MIN = 2.0 de
 * .maestro/ferramentas/gate_1d_salao.py:53.
 *
 * Corredores (y em unidades do viewBox, contra caixa pintada):
 *   130–140  moldura (borda, y=130) → pedra bruta 143,65 ... folga 3,61
 *   378–448  facetas 374,5          → "fonte · B3" 452,73 . folga 2,72
 *   490–516  "data · …" 485,02      → punção EM VIAGEM 522  folga 5,52
 *   570–590  punção 566             → citação 594,67 ...... folga 3,25
 *   616–627  citação 611,58         → mini-chip 630 ....... folga 2,25
 * Os vãos 211,26–214,62 · 234,12–243,75 · 256,75–267,5 foram DESCARTADOS:
 * com 2px de folga de cada lado sobrariam −0,6 / 5,6 / 6,7px, e um toco
 * de 6px com stroke 1,5 lê como sujeira, não como espinha (regra: só
 * emite segmento com comprimento >= 8px).
 *
 * RESSALVA DE NÚMERO (ARREMATE raia H, não é geometria a corrigir): o
 * segmento 2 fica em [378,448] por decisão do maestro. A raia anterior
 * mediu que a maior fatia de espinha removida sobre TELA VAZIA é 22,80
 * unidades (y 448,05–470,85), não os 10,75 da manchete de R15 — R15 usou
 * a extensão Y do texto "fonte · B3" sem conferir a extensão X (a caixa
 * dele para em x=456, antes da banda pintada da espinha em 459,25), e o
 * primeiro ator que de fato cruza a coluna é "data · 08/07/2026" em
 * y=470,87. Esticar o segmento até ~468,8 fecharia o vão, MAS sob
 * fallback de fonte +10% o "fonte · B3" cresce para x≈462,6 e passaria a
 * cruzar a coluna. O maestro ACEITOU o vão de 22,80 e mandou corrigir o
 * NÚMERO da ressalva, não a geometria.
 *
 * TERCEIRO SEGMENTO — ENCURTADO DE 546 PARA 516 (ARREMATE raia H, a 2ª
 * violação que sobrara na regra de ferro). A espinha é ESTÁTICA e irmã
 * dos [data-plano]; a punção NÃO é: NascimentoScrub.tsx:294-296 roda
 * `fromTo(puncao, { y: -28 }, { y: 0 })` no plano 6, então o rect
 * (CenaNascimento.tsx:304 — x 444, y 550, 32×16) VIAJA com a aresta
 * superior indo de y=522 (início do tween) a y=550 (repouso) e a
 * inferior de 538 a 566. A faixa de viagem [522,566] engolia o fim do
 * antigo [490,546]: o gate mediu a espinha atravessando a punção de
 * lado a lado — corda 17,25px / 16,00 unidades, prof 6,13px, em
 * `/` 1440×900 p=0.6 (opacidade da caixa 0,278 ⇒ y ≈ −20,2) e o mesmo
 * cruzamento a 390×844 (corda 15,99 uu, opacidade 0,087 ⇒ y ≈ −25,6);
 * mais um `ponta_sem_folga` com o fim do segmento 0,29px DENTRO da
 * punção em viagem.
 *   ESCOLHA DO CORTE (medida, não chute — as duas opções foram rodadas no
 *   varredor). Parar em 519 já zera o cruzamento e já paga FOLGA_MIN em
 *   UNIDADES DE USUÁRIO — o espaço em que este `d` é escrito e em que o
 *   stroke é definido, que é o espaço normativo para folga por
 *   arbitragem do maestro: 522 − 519 = 3,0 un de vão, lidos pelo gate
 *   como folga 2,50 un. MAS a 390×844 o SVG desce à escala 0,3891 e
 *   essas mesmas unidades viram 1,93px de viewport — 0,07px abaixo do
 *   piso — e o segmento seguia aparecendo no relatório como
 *   `ponta_sem_folga`. Parar em 516 custa TRÊS unidades a mais de
 *   espinha e compra folga 5,52 un = 2,15px a 0,3891 e 5,95px a 1,0783:
 *   o segmento passa a limpo nos DOIS sistemas de coordenadas, e a
 *   disputa "user units ou px de viewport" deixa de tocá-lo. Sobram 26
 *   unidades de segmento, acima do piso de 8.
 *   ATENÇÃO ao que NÃO era o culpado: a punção entra POR CIMA (y −28 =
 *   28 unidades ACIMA do repouso) e nunca desce abaixo de 566, então o
 *   segmento [570,590] — que fica entre a punção em repouso e a citação
 *   — jamais é atravessado por ela. Ele fica INTOCADO.
 *
 * Decorativa e ESTÁTICA: nenhum seletor de NascimentoScrub.tsx:157-188 a
 * lê (nem classe, nem data-attr, nem [data-plano] — a <line> é IRMÃ dos
 * grupos de plano, não filha), então 1 → 5 nós é inobservável pela
 * timeline. Seguem sendo os PRIMEIROS filhos do <svg>: ordem de pintura
 * idêntica, a espinha continua por baixo de todos os atores.
 */
const ESPINHA = [
  [130, 140],
  [378, 448],
  [490, 516],
  [570, 590],
  [616, 627],
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
  /**
   * §7-B2: true = o `<ol>` de legendas é VISÍVEL (landing — letreiro da
   * cena, estilizado por cinema/nascimento.css). Default false = sr-only,
   * comportamento herdado (/como-funciona NÃO passa a prop: byte-idêntica
   * na apresentação, exceto os 8 planos estáticos do próprio diagrama).
   */
  legendasVisiveis?: boolean;
};

export function CenaNascimento({ className, legendasVisiveis = false }: PropsCenaNascimento) {
  const papel = exemplosProntos()[0];
  const dado = `${papel.ticker} · ${formatPct(papel.participacaoPct)}% do IBOV`;
  const dataFmt = formatDataIso(DATA_CARTEIRA_IBOV);
  // Mesma anatomia de citação já aprovada em #prova/hero (D37): o carimbo
  // "[1] B3 · Carteira teórica do Ibovespa · {data}".
  const citacao = `[1] B3 · Carteira teórica do Ibovespa · ${dataFmt}`;

  const cxGema = 460;
  const cyGema = 340;
  const facetas = facetasPath(cxGema, cyGema, 72, 34);

  // Selos: 6 centros distribuídos na moldura da mina; índice 0 = B3 (E12).
  const selosX = [100, 244, 388, 532, 676, 820];
  const selCyBase = 92;

  return (
    <>
      <figure
        role="img"
        aria-label="Diagrama: como um número público entra na tese, das fontes oficiais até a citação carimbada."
        className={className ? `nascimento-figura ${className}` : "nascimento-figura"}
      >
        <svg
          viewBox="0 0 920 690"
          className="nascimento-svg"
          aria-hidden="true"
          focusable="false"
        >
          {/* Espinha central — conecta os planos, sempre visível
              (decorativo). 5 trechos em corredor vazio: ver ESPINHA acima.
              A classe é a MESMA (lapidacao.css:52-55 vale para 1 ou para 5
              elementos sem nenhuma alteração: a folha é global e não se
              toca). */}
          {ESPINHA.map(([y1, y2]) => (
            <line
              key={y1}
              x1={cxGema}
              y1={y1}
              x2={cxGema}
              y2={y2}
              className="nascimento-esteira"
            />
          ))}

          {/* PLANO 1 — as fontes: moldura + 6 selos (E12: B3 é o índice 0). */}
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
            {/* Linha de extração — sai do selo B3 (índice 0) rumo à pedra
                bruta, nascendo e morrendo na BORDA (padrão naBorda() do
                Salão, SalaoDimensoes.tsx:203-209). R1/V3, ruling R15: o `d`
                antigo terminava em (440,150), 2,8px DENTRO do polígono da
                pedra (a aresta (420,150)→(470,143) está em y=147,2 nesse x),
                e nascia em (100,116), sobre o anel PINTADO do selo (r 24 +
                stroke 2,5 → raio pintado 25,25) e por cima da caixa do
                rótulo "B3" (getBBox x 93,6–106,4 / y 121,75–134,75).
                  P3: ponto da aresta em x=440 deslocado 3,5px pela normal
                      externa (−0,1386, −0,9903) → (439,5 , 143,7). Os 3,5px
                      são 0,75 (meio traço da pedra) + 2,0 (folga naBorda) +
                      0,75 (meio traço da própria linha) ⇒ gap entre faces
                      pintadas = 2,0px exatos.
                  P0: naBorda do selo a raio 29 (= 25,25 pintado + 2,0 folga
                      + 0,75 meio-traço), saindo 25° a leste do sul → o
                      +12,3/+26,3 abaixo. O desvio a leste é o que tira a
                      curva de cima do rótulo "B3": x=112,3 limpa a borda
                      direita do rótulo (106,4) por 5,9px. Saída a 0° (sul
                      puro) cairia dentro da caixa do rótulo, que é centrada
                      no mesmo x do selo — por isso P0 também entrou.
                  C1 acompanha P0 em x para a tangente de saída seguir
                      vertical; C2 (380,130) INTOCADO.
                CONTINUA SENDO UM ÚNICO <path>: NascimentoScrub.tsx:163-165
                usa querySelector — dividir quebraria a timeline em silêncio.
                Só o atributo `d` muda; o tween de lá é `opacity` (:252),
                independente de geometria (path-morph é PROIBIDO, :15-17).
                Folga mínima na curva inteira, amostrada a 2px: 2,79px. */}
            <path
              d={`M ${selosX[0] + 12.3} ${selCyBase + 26.3} C ${selosX[0] + 12.3} 162, 380 130, 439.5 143.7`}
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

          {/* PLANO 4 — a conferência: o aro fecha sobre as duas provas
              (fonte · data). Split do antigo plano 4 (§3-C3/§7-B5). */}
          <g data-plano="4" className="nascimento-plano nascimento-plano--gate">
            <circle cx={330} cy={470} r={38} className="nascimento-aro" />
            <text x={390} y={464} className="nascimento-legenda-mono">
              fonte · B3
            </text>
            <text x={390} y={482} className="nascimento-legenda-mono">
              data · {dataFmt}
            </text>
          </g>

          {/* PLANO 5 — a contraprova: a 2ª pedra SEM selo vai à bandeja de
              lacuna declarada (o beat da postura regulatória, agora com
              tempo próprio — split do antigo plano 4). */}
          <g data-plano="5" className="nascimento-plano nascimento-plano--contraprova">
            <g className="nascimento-bandeja">
              <rect x={590} y={440} width={130} height={62} rx={6} />
              <path d="M 622 458 L 648 452 L 668 466 L 660 484 L 630 486 L 616 470 Z" className="nascimento-pedra-lacuna" />
              <text x={655} y={520} textAnchor="middle" className="nascimento-legenda-mono">
                sem fonte → lacuna declarada
              </text>
            </g>
          </g>

          {/* PLANO 6 — o carimbo: punção crava, citação completa imprime. */}
          <g data-plano="6" className="nascimento-plano nascimento-plano--carimbo">
            <rect x={444} y={550} width={32} height={16} rx={2} className="nascimento-puncao" />
            <text x={460} y={608} textAnchor="middle" className="nascimento-citacao">
              {citacao}
            </text>
          </g>

          {/* PLANO 7 — o engaste: a gema pousa no mini-chip. */}
          <g data-plano="7" className="nascimento-plano nascimento-plano--engaste">
            <g className="nascimento-mini-chip">
              <rect x={410} y={630} width={100} height={44} rx={4} className="nascimento-mini-chip-fundo" />
              <path d="M 410 630 L 480 630 M 410 630 L 410 674" className="nascimento-mini-chip-aresta" />
              <path d="M 510 630 L 440 674 M 510 674 L 510 630" className="nascimento-mini-chip-quilha" />
            </g>
            <circle cx={460} cy={652} r={13} className="nascimento-gema-final" />
          </g>

          {/* PLANO 8 — a trilha (novo, §7-B5): o traço pontilhado refaz o
              caminho de trás para frente (gema → conferência → extração →
              selo B3), com 3 pontos de registro e a seta de retorno — tudo
              na faixa vazia à esquerda do desenho (vb x<250: nunca sobre
              dado/citação/rótulos). O fio de saída (consertado: dasharray 1
              + pathLength 1) se desenha e termina em y=686 (≤686, §7-B5). */}
          <g data-plano="8" className="nascimento-plano nascimento-plano--trilha">
            <path
              d="M 404 660 C 330 664, 268 646, 248 606 C 214 554, 214 432, 222 380 C 230 330, 240 290, 196 234"
              className="nascimento-trilha"
              data-trilha=""
            />
            <circle cx={296} cy={648} r={3} className="nascimento-trilha-ponto" />
            <circle cx={219} cy={493} r={3} className="nascimento-trilha-ponto" />
            <circle cx={228} cy={330} r={3} className="nascimento-trilha-ponto" />
            <path d="M 207 246 L 194 232 L 211 226" className="nascimento-trilha-seta" />
            <path
              d="M 460 674 L 460 686"
              pathLength={1}
              className="nascimento-fio-saida"
              data-fio-saida=""
            />
          </g>
        </svg>
      </figure>

      {/* FORA do figure (§7-B1: descendentes de role=img são apresentacionais
          para AT): o h3 e as 8 legendas — FONTE ÚNICA (E-A3). Copy BYTE-FIEL
          de .maestro/copy-ourivesaria.md §1 (ruling 6.6: sr-only conta no
          gate; números interpolados de exemplosProntos()/DATA_CARTEIRA_IBOV,
          jamais literais). Na landing (legendasVisiveis) o <ol> é o letreiro
          da cena; nas demais superfícies segue sr-only. */}
      <h3 className="sr-only">Como um número nasce na tese, em oito passos</h3>
      <ol className={legendasVisiveis ? "nascimento-legendas" : "sr-only"}>
        <li>
          {"Seis fontes oficiais abastecem a tese: B3, CVM, SEC, BCB, Banco Mundial e Tesouro. Só entra o que é público e datado."}
        </li>
        <li>{`Da B3 sai o dado cru: ${dado}, do jeito que foi publicado em ${dataFmt}.`}</li>
        <li>
          {"Cinco dimensões cortam o mesmo dado: fundamentos, pares globais, macro Brasil, macro global e elos causais. Nenhuma decide sozinha."}
        </li>
        <li>
          {"A conferência pede duas provas de cada número: fonte e data. Sem as duas, o número não passa."}
        </li>
        <li>
          {"A contraprova: o que a fonte pública não tem vira lacuna declarada — nunca vira estimativa."}
        </li>
        <li>{`O carimbo crava a citação no texto: ${citacao} — quem afirmou, apurado quando.`}</li>
        <li>
          {"O número assenta na tese com o selo de origem ao lado — pronto para ser conferido, não acreditado."}
        </li>
        <li>
          {"A trilha fica registrada no fim do documento: você pode refazer o caminho inteiro de trás para frente."}
        </li>
      </ol>
    </>
  );
}
