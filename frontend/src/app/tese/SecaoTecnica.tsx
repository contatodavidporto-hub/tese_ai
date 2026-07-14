// Seção "Análise técnica" — indicadores descritivos (RSI/MACD/Bollinger/
// médias/estocástico/Williams/A-D/Fibonacci) + os gráficos correspondentes,
// na ORDEM CANÔNICA do contrato (`ORDEM_CANONICA_GRAFICOS`). A nota
// "preços não ajustados por proventos" fica visível no topo E de novo em
// cada gráfico (`GraficoLinha/Macd/Oscilador` já a repetem via `NotaFixa`) —
// redundância intencional: um leitor que só rola até um gráfico específico
// ainda vê o aviso sem precisar subir a página.

import { Reveal } from "@/components/motion/Reveal";
import { TermoTooltip } from "@/components/ui/TermoTooltip";

import { FonteChip, NotaFixa, RotuloChip } from "./EnvelopeNovo";
import { formatarValor } from "./formatacao";
import { GraficoTese } from "./GraficoTese";
import { BadgeLacuna } from "./SecaoChrome";
import { ORDEM_CANONICA_GRAFICOS, type Grafico, type Tecnica } from "./types";

function ordenarGraficos(graficos: Grafico[]): Grafico[] {
  const posicao = new Map<string, number>(ORDEM_CANONICA_GRAFICOS.map((id, i) => [id, i]));
  return [...graficos].sort((a, b) => (posicao.get(a.id) ?? ORDEM_CANONICA_GRAFICOS.length) - (posicao.get(b.id) ?? ORDEM_CANONICA_GRAFICOS.length));
}

// Missão APOTEOSE (crit. 11, D7): o NOME do indicador (RSI, MACD, Bandas de
// Bollinger…) vira gatilho de `TermoTooltip` com a definição REAL do payload
// (`o_que_mede`) — zero definição inventada; sem definição => texto puro
// (fallback silencioso). Mesma decisão de SecaoMetricasSetor: a definição
// saiu do corpo do card para o tooltip (evita a string duplicada colada ao
// termo); `leitura` (template determinístico, já passou pelo gate) e
// `detalhe` seguem visíveis e intocados.
function CardIndicador({ indicador }: { indicador: Tecnica["indicadores"][number] }) {
  const valorFmt = formatarValor(indicador.valor, indicador.unidade);
  return (
    <div className="flex flex-col gap-2 border border-line bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-display text-lede font-semibold text-ink">
          <TermoTooltip termo={indicador.nome} definicao={indicador.o_que_mede?.trim() || undefined}>
            {indicador.nome}
          </TermoTooltip>
        </h4>
        {valorFmt ? (
          <span className="font-mono text-h3 font-semibold text-brasa-texto">{valorFmt}</span>
        ) : (
          <BadgeLacuna texto="Dado não encontrado" />
        )}
      </div>
      {indicador.detalhe && <p className="font-mono text-meta text-ink-3">{indicador.detalhe}</p>}
      <p className="text-body text-ink">{indicador.leitura}</p>
    </div>
  );
}

export function SecaoTecnica({ tecnica, graficos }: { tecnica: Tecnica; graficos: Grafico[] }) {
  const graficosOrdenados = ordenarGraficos(graficos);

  return (
    <div className="flex flex-col gap-6">
      <NotaFixa texto={tecnica.nota} />

      {tecnica.indicadores.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {tecnica.indicadores.map((ind, i) => (
            <CardIndicador key={i} indicador={ind} />
          ))}
        </div>
      )}

      {graficosOrdenados.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* `.entrada-grafico` (§5, direcao-de-arte-cinema.md): variante do
              Reveal que NÃO estiliza o wrapper em si (ao contrário de
              `.reveal`/`.reveal-ticker` — aqui é só um GATE de is-armed/
              is-revealed para os seletores `.traco-grafico*` dentro do SVG,
              globals.css). Cada gráfico entra em cena 1x, sozinho, quando o
              PRÓPRIO card alcança o scroll — nunca os 6 juntos: por isso
              cada um recebe seu próprio `<Reveal>` aqui, em vez de herdar
              só o fade único de `SecaoEnvelope` (que cobre a seção inteira,
              não teria como escopar por gráfico individual).

              Missão MATÉRIA VIVA (Onda 1E): em browsers com
              @supports (animation-timeline: view()), o desenho das séries
              passa a ser SCRUBBED pelo scroll — `.grafico-scrub` no
              <figure> de cada gráfico + cinema/graficos.css, zero JS novo.
              Este <Reveal variant="entrada-grafico"> PERMANECE intacto
              como fallback one-shot (Firefox <155/sem suporte): animation
              vence transition na mesma propriedade, convivência limpa —
              nada a mudar aqui. */}
          {graficosOrdenados.map((g) => (
            <Reveal key={g.id} variant="entrada-grafico">
              <GraficoTese grafico={g} />
            </Reveal>
          ))}
        </div>
      )}

      {tecnica.indicadores.length === 0 && graficosOrdenados.length === 0 && (
        <p className="text-ui text-ink-2">Nenhum indicador técnico computado para este ativo.</p>
      )}

      <FonteChip fonte={tecnica.fonte} />

      {tecnica.lacunas.length > 0 && (
        <div className="flex flex-col gap-2 border-l-4 border-aviso-borda bg-aviso-fundo/30 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <BadgeLacuna texto="Dado não encontrado" />
            <RotuloChip texto="Lacunas da análise técnica" />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-ui text-aviso-texto">
            {tecnica.lacunas.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
