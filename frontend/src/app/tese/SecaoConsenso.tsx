// Seção "Consenso de analistas" — itens tratados como CITAÇÃO (mesma
// linguagem visual da lista "Citações" em TeseView.tsx: `bg-realce`, borda
// de citação), no template canônico do contrato ("Segundo {veículo}
// ({data}), {casa} tem preço-alvo de R$ {valor}") — é o MESMO texto que o
// gate v3 varre (`texto_varredura`, correção A5/contrato §"Varredura do
// gate") para casar o valor citado com `envelope["consenso"]`; manter a
// exibição fiel ao template não é só estética, é o que faz R12 aceitar a
// frase como atribuída.
//
// `rel="noopener noreferrer nofollow"`: diferente de `FonteLink`/citações da
// tese (fontes primárias registradas, B3/CVM/BCB — recebem `noopener
// noreferrer` simples), estes são links para OPINIÃO DE TERCEIRO (matéria de
// veículo de imprensa reportando o preço-alvo de uma casa) — `nofollow`
// sinaliza "não endosso" também para buscadores, coerente com o aviso da
// própria seção ("a plataforma reporta, não endossa").
//
// Missão APOTEOSE (crit. 11 — decisão registrada): NENHUM TermoTooltip
// nesta seção. O texto dos itens é o `texto_varredura` que o gate v3 varre
// (INTOCÁVEL — envolver qualquer palavra dele num <button> mudaria o texto
// renderizado que o R12 aceita como atribuído), e o chrome restante
// (aviso/lacunas/meta) não tem campo definicional no payload — termo sem
// definição = fallback silencioso, sem tooltip (D7).

import { RotuloChip } from "./EnvelopeNovo";
import { formatarData, formatarValorLivre } from "./formatacao";
import { AvisoBanner, BadgeLacuna } from "./SecaoChrome";
import type { Consenso, ItemConsenso } from "./types";

function urlHttp(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

function ItemConsensoCard({ item }: { item: ItemConsenso }) {
  const valorFmt = formatarValorLivre(item.valor, item.moeda);
  const dataMateriaFmt = item.data_materia ? formatarData(item.data_materia) : null;
  const casaTexto = item.casa ?? "o consenso consultado";

  return (
    <li className="flex flex-col gap-1.5 bg-realce py-4 pl-5 pr-4">
      <p className="text-body text-ink">
        Segundo{" "}
        {urlHttp(item.url) ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="font-medium text-ink underline decoration-line-strong underline-offset-2 hover:decoration-brasa-texto"
          >
            {item.veiculo}
          </a>
        ) : (
          <span className="font-medium text-ink">{item.veiculo}</span>
        )}
        {dataMateriaFmt && ` (${dataMateriaFmt})`}, {casaTexto} tem preço-alvo de{" "}
        <span className="font-mono font-semibold text-brasa-texto">{valorFmt ?? "dado não encontrado"}</span>.
      </p>
      <p className="font-mono text-meta text-ink-2">
        {item.titulo} · consultado em {formatarData(item.data_busca)}
      </p>
    </li>
  );
}

export function SecaoConsenso({ consenso }: { consenso: Consenso }) {
  return (
    <div className="flex flex-col gap-6">
      <AvisoBanner aviso={consenso.aviso} />

      {consenso.itens.length > 0 ? (
        <ol className="flex flex-col gap-3 stagger">
          {consenso.itens.map((item, i) => (
            <ItemConsensoCard key={i} item={item} />
          ))}
        </ol>
      ) : (
        <p className="text-ui text-ink-2">Nenhuma opinião de terceiro com atribuição válida encontrada.</p>
      )}

      {consenso.lacunas.length > 0 && (
        <div className="flex flex-col gap-2 border-l-4 border-aviso-borda bg-aviso-fundo/30 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <BadgeLacuna texto="Dado não encontrado" />
            <RotuloChip texto="Lacunas do consenso" />
          </div>
          <ul className="list-disc space-y-1 pl-5 text-ui text-aviso-texto">
            {consenso.lacunas.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
