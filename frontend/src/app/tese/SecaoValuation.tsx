// Seção "Valuation" — SEMPRE o aviso "NÃO é preço-alvo nem recomendação" em
// destaque (mesmo peso visual da tarja CVM, via `AvisoBanner` reaproveitado),
// depois cada modelo com premissas rotuladas, cenários (conservador/base/
// otimista) e a tabela de sensibilidade em seu PRÓPRIO scroll horizontal
// (`overflow-x-auto` local — não deixa a tabela empurrar a página inteira
// para o lado em telas estreitas).
//
// Missão APOTEOSE (crit. 11, D7 — decisão registrada): NENHUM TermoTooltip
// aqui. O contrato de valuation não traz campo definicional (`o_que_mede`
// não existe em modelo/premissa/cenário; `descricao` do modelo já é visível
// no card) e inventar definição no front é proibido — termo sem definição
// de payload = fallback SILENCIOSO (sem tooltip). Se um dia o glossário
// curado (`lib/glossario.ts`, dono COPY) cobrir "Gordon/DDM"/"custo de
// capital", o aproveitamento é follow-up de integração, não desta onda.

import { RotuloChip } from "./EnvelopeNovo";
import { formatarValorLivre } from "./formatacao";
import { AvisoBanner, BadgeLacuna } from "./SecaoChrome";
import type { CenarioValuation, ModeloValuation, Valuation } from "./types";

const ROTULO_CENARIO: Record<CenarioValuation["nome"], string> = {
  conservador: "Conservador",
  base: "Base",
  otimista: "Otimista",
};

function CartaoCenario({ cenario, unidadeFaixa }: { cenario: CenarioValuation; unidadeFaixa: string }) {
  const valorFmt = formatarValorLivre(cenario.valor, cenario.unidade || unidadeFaixa);
  return (
    <div className="flex flex-col gap-1.5 border border-line p-4">
      <span className="font-sans text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
        {ROTULO_CENARIO[cenario.nome] ?? cenario.nome}
      </span>
      <span className="text-meta text-ink-3">{cenario.parametros}</span>
      {valorFmt ? (
        <span className="font-mono text-h3 font-semibold text-brasa-texto">{valorFmt}</span>
      ) : (
        <div className="flex flex-col gap-1">
          <BadgeLacuna texto="Dado não encontrado" />
          {cenario.omitido && <span className="text-ui text-aviso-texto">{cenario.omitido}</span>}
        </div>
      )}
    </div>
  );
}

function TabelaSensibilidade({ modelo }: { modelo: ModeloValuation }) {
  const s = modelo.sensibilidade;
  if (!s) return null;
  const unidadeCelula = modelo.faixa?.unidade ?? "";
  return (
    <div className="flex flex-col gap-2">
      <p className="text-ui text-ink-2">
        Sensibilidade — linhas: <span className="font-medium text-ink">{s.eixo_linhas}</span> · colunas:{" "}
        <span className="font-medium text-ink">{s.eixo_colunas}</span>
      </p>
      {/* Scroll horizontal PRÓPRIO desta tabela (não da página) — tabelas de
          sensibilidade podem ter várias colunas de cenário em telas estreitas. */}
      <div className="overflow-x-auto border border-line">
        <table className="w-full min-w-max border-collapse font-mono text-ui text-ink">
          <thead>
            <tr className="border-b-2 border-line-strong">
              <th scope="col" className="px-3 py-2 text-left font-sans text-label uppercase tracking-[0.08em] text-ink-3">
                {s.eixo_linhas} \ {s.eixo_colunas}
              </th>
              {s.colunas.map((c, j) => (
                <th key={j} scope="col" className="px-3 py-2 text-right font-sans text-label uppercase tracking-[0.08em] text-ink-3">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {s.linhas.map((linha, i) => (
              <tr key={i} className="border-b border-line">
                <th scope="row" className="px-3 py-2 text-left font-sans text-ui font-medium text-ink-2">
                  {linha}
                </th>
                {(s.celulas[i] ?? []).map((v, j) => {
                  const fmt = formatarValorLivre(v, unidadeCelula);
                  return fmt ? (
                    <td key={j} className="px-3 py-2 text-right">
                      {fmt}
                    </td>
                  ) : (
                    <td key={j} className="hachura-lacuna px-3 py-2 text-center align-middle font-mono text-meta text-aviso-texto">
                      dado não encontrado
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CartaoModelo({ modelo }: { modelo: ModeloValuation }) {
  return (
    <div className="flex flex-col gap-4 border border-line bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-1">
        <h4 className="font-display text-h3 font-semibold tracking-tight text-ink">{modelo.nome}</h4>
        <p className="max-w-[68ch] text-ui text-ink-2">{modelo.descricao}</p>
      </div>

      {modelo.omitido ? (
        <div className="flex flex-wrap items-center gap-3">
          <BadgeLacuna texto="Modelo não computado" />
          <p className="text-ui text-aviso-texto">{modelo.omitido}</p>
        </div>
      ) : (
        <>
          {modelo.premissas.length > 0 && (
            <div className="flex flex-col gap-2">
              <h5 className="font-sans text-label font-semibold uppercase tracking-[0.1em] text-ink-3">Premissas</h5>
              <ul className="flex flex-col gap-1.5">
                {modelo.premissas.map((p, i) => (
                  <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-ui text-ink-2">
                    <span className="font-medium text-ink">{p.nome}:</span>
                    <span className="font-mono text-brasa-texto">{p.valor}</span>
                    <RotuloChip texto={p.rotulo} />
                    <span className="text-meta text-ink-3">{p.origem}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {modelo.cenarios.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-3">
              {modelo.cenarios.map((c) => (
                <CartaoCenario key={c.nome} cenario={c} unidadeFaixa={modelo.faixa?.unidade ?? ""} />
              ))}
            </div>
          )}

          {modelo.faixa && (
            <p className="flex flex-wrap items-baseline gap-2">
              <span className="font-sans text-label font-semibold uppercase tracking-[0.1em] text-ink-3">
                Faixa de sensibilidade
              </span>
              <span className="font-mono text-h2 font-semibold text-brasa-texto">
                {formatarValorLivre(modelo.faixa.min, modelo.faixa.unidade)} –{" "}
                {formatarValorLivre(modelo.faixa.max, modelo.faixa.unidade)}
              </span>
            </p>
          )}

          <TabelaSensibilidade modelo={modelo} />
        </>
      )}
    </div>
  );
}

export function SecaoValuation({ valuation }: { valuation: Valuation }) {
  return (
    <div className="flex flex-col gap-6">
      <AvisoBanner aviso={valuation.aviso} />

      {valuation.modelos.length > 0 ? (
        <div className="flex flex-col gap-6">
          {valuation.modelos.map((m, i) => (
            <CartaoModelo key={i} modelo={m} />
          ))}
        </div>
      ) : (
        <p className="text-ui text-ink-2">Nenhum modelo de valuation computado para este ativo.</p>
      )}

      {valuation.lacunas.length > 0 && (
        <div className="flex flex-col gap-2 border-l-4 border-aviso-borda bg-aviso-fundo/30 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <BadgeLacuna texto="Dado não encontrado" />
            <RotuloChip texto="Lacunas do valuation" />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-ui text-aviso-texto">
            {valuation.lacunas.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}

      <FonteRastreioValuation />
    </div>
  );
}

// A fonte de cada modelo já vem embutida em `premissas[].origem` (o
// contrato não tem um `fonte`/`FonteRef` a nível de modelo/valuation — só
// premissa por premissa) — este rótulo final apenas reforça de onde vêm os
// números por extenso, sem inventar uma fonte agregada que o contrato não
// define.
function FonteRastreioValuation() {
  return (
    <p className="text-meta text-ink-3">
      Cada premissa lista sua origem ao lado (COTAHIST, DFP, CAPM, etc.) — não há uma fonte única agregada para
      valuation: é um exercício de cálculo sobre dados já citados alhures nesta tese.
    </p>
  );
}
