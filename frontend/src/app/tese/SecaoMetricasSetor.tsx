// Seção "Métricas do setor" — cartões com fórmula + o que mede + implicação
// NEUTRA + fonte(s) + rótulos de proveniência (ex.: "prudencial", "aprox.").
// Diferente de Tecnica/Valuation/Consenso, `metricas_setor` é um ARRAY puro
// no contrato (sem `aviso`/`lacunas` de nível de seção) — cada métrica
// carrega sua própria `lacuna` quando `valor` é `null`.

import { FonteChip, RotuloChip } from "./EnvelopeNovo";
import { formatarValor } from "./formatacao";
import { BadgeLacuna } from "./SecaoChrome";
import type { MetricaSetor } from "./types";

function CardMetrica({ metrica }: { metrica: MetricaSetor }) {
  const valorFmt = formatarValor(metrica.valor, metrica.unidade);
  return (
    <div className="flex flex-col gap-2 border border-line bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-display text-lede font-semibold text-ink">{metrica.nome}</h4>
        {valorFmt ? (
          <span className="font-mono text-h3 font-semibold text-brasa-texto">{valorFmt}</span>
        ) : (
          <BadgeLacuna texto="Dado não encontrado" />
        )}
      </div>
      <p className="font-mono text-meta text-ink-3">Fórmula: {metrica.formula}</p>
      <p className="text-ui text-ink-2">{metrica.o_que_mede}</p>
      <p className="text-body text-ink">{metrica.implicacao}</p>
      {metrica.lacuna && <p className="text-ui text-aviso-texto">{metrica.lacuna}</p>}
      {metrica.rotulos.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {metrica.rotulos.map((r, i) => (
            <RotuloChip key={i} texto={r} />
          ))}
        </div>
      )}
      {metrica.fontes.length > 0 && (
        <div className="flex flex-col gap-0.5 border-t border-line pt-2">
          {metrica.fontes.map((f, i) => (
            <FonteChip key={i} fonte={f} />
          ))}
        </div>
      )}
    </div>
  );
}

export function SecaoMetricasSetor({ metricas }: { metricas: MetricaSetor[] }) {
  if (metricas.length === 0) {
    return <p className="text-ui text-ink-2">Nenhuma métrica de setor computada para este ativo.</p>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {metricas.map((m, i) => (
        <CardMetrica key={i} metrica={m} />
      ))}
    </div>
  );
}
