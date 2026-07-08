import Link from "next/link";
import { Suspense } from "react";

import { ChipSaude, ChipSaudeAoVivo, Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { DATA_CARTEIRA_IBOV, exemplosProntos } from "@/lib/tickers";

// Renderização dinâmica: necessária para o CSP com nonce por requisição (src/proxy.ts)
// ser aplicado em cada resposta.
export const dynamic = "force-dynamic";

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

const DIMENSOES = [
  {
    numero: "01",
    titulo: "Fundamentos",
    texto:
      "Demonstrações e cadastro públicos da CVM: receita, margens, dívida e as derivadas que o dado permite calcular — nada além do que a fonte sustenta.",
  },
  {
    numero: "02",
    titulo: "Contexto macro",
    texto:
      "Séries oficiais do Banco Central do Brasil, FRED e Banco Mundial: juros, câmbio e atividade, com o rótulo e a data de cada série.",
  },
  {
    numero: "03",
    titulo: "Pares globais",
    texto:
      "Comparáveis internacionais a partir de arquivos da SEC — sempre com a ressalva de padrão contábil e moeda, como comparação selecionada, não equivalência.",
  },
  {
    numero: "04",
    titulo: "Geopolítica e correlações",
    texto:
      "Elos causais entre evento, commodity, setor e empresa — marcados como interpretação, em cenários condicionais, com fonte nas duas pontas de cada elo.",
  },
] as const;

const PRINCIPIOS = [
  {
    titulo: "Não recomenda",
    texto:
      "Nenhum “compre”, “venda” ou preço-alvo. A ferramenta estrutura o raciocínio; a decisão é do leitor — postura alinhada à regulação da CVM.",
  },
  {
    titulo: "Cada número com fonte",
    texto:
      "As afirmações factuais saem ancoradas em citações verificáveis, com link e data da fonte pública. O que não tem fonte não entra como fato.",
  },
  {
    titulo: "Lacunas declaradas",
    texto:
      "Quando o dado não existe, a tese registra “dado não encontrado” e segue — abster é mais honesto que estimar.",
  },
] as const;

export default function Home() {
  const exemplos = exemplosProntos();

  return (
    <>
      <Header />
      <main id="conteudo" className="flex-1">
        {/* Herói */}
        <section className="border-b border-linha">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-start gap-6 px-4 py-16 sm:px-6 sm:py-24">
            <p className="animate-entrada font-mono text-xs uppercase tracking-[0.2em] text-selo-texto">
              Teses de investimento · B3
            </p>
            <h1 className="max-w-3xl animate-entrada font-display text-4xl font-semibold leading-tight tracking-tight text-tinta [animation-delay:80ms] sm:text-6xl">
              A tese inteira, com a fonte de cada número.
            </h1>
            <p className="max-w-2xl animate-entrada text-base leading-relaxed text-tinta-2 [animation-delay:160ms] sm:text-lg">
              O Tese AI estrutura teses de investimento cruzando fundamentos,
              contexto macro, pares globais e geopolítica. Cada afirmação
              factual é rastreável até o dado público de origem, interpretação
              vem rotulada como tal — e cada lacuna é declarada, nunca
              preenchida com chute.
            </p>
            <div className="flex animate-entrada flex-wrap items-center gap-3 [animation-delay:240ms]">
              <Link
                href="/tese"
                className="rounded-lg bg-selo px-6 py-3 text-sm font-semibold text-sobre-selo transition-colors hover:bg-selo-forte"
              >
                Gerar tese
              </Link>
              <Link
                href={`/tese?ticker=${encodeURIComponent(exemplos[0]?.ticker ?? "VALE3")}`}
                className="rounded-lg border border-borda-campo px-6 py-3 text-sm font-medium text-tinta transition-colors hover:border-selo-texto"
              >
                Ver exemplo: {exemplos[0]?.ticker ?? "VALE3"}
              </Link>
            </div>
            <p className="animate-entrada text-xs text-tinta-3 [animation-delay:320ms]">
              Ferramenta de estruturação — não é recomendação de compra ou venda.
            </p>
          </div>
        </section>

        {/* Galeria de exemplos prontos */}
        <section aria-labelledby="galeria-titulo" className="border-b border-linha">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-14 sm:px-6">
            <div className="flex flex-col gap-2">
              <h2
                id="galeria-titulo"
                className="font-display text-2xl font-semibold tracking-tight text-tinta sm:text-3xl"
              >
                Teses de exemplo — abrem na hora
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-tinta-2">
                Pré-geradas pelo motor para os 10 maiores pesos da carteira
                teórica do Ibovespa (B3, {formatDataIso(DATA_CARTEIRA_IBOV)}) e
                mantidas em cache. Clique e leia a tese completa, com citações e
                fontes — se o cache tiver expirado, ela é regenerada na hora.
              </p>
            </div>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {exemplos.map((papel) => (
                <li key={papel.ticker} className="animate-entrada">
                  {/* stagger via classe utilitária, nunca style inline (CSP estrito) */}
                  <Link
                    href={`/tese?ticker=${encodeURIComponent(papel.ticker)}`}
                    className="group flex h-full flex-col gap-1 rounded-xl border border-linha bg-cartao p-4 transition-all hover:-translate-y-0.5 hover:border-selo-texto"
                  >
                    <span className="font-mono text-lg font-bold tracking-tight text-tinta">
                      {papel.ticker}
                    </span>
                    <span className="truncate text-xs text-tinta-2">
                      {papel.nome}
                    </span>
                    {papel.participacaoPct > 0 && (
                      <span className="font-mono text-[0.65rem] text-tinta-3">
                        {papel.participacaoPct.toLocaleString("pt-BR", {
                          minimumFractionDigits: 1,
                          maximumFractionDigits: 1,
                        })}
                        % do IBOV
                      </span>
                    )}
                    <span className="mt-2 text-xs font-medium text-selo-texto opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                      Abrir tese →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* As quatro dimensões */}
        <section aria-labelledby="dimensoes-titulo" className="border-b border-linha">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <div className="flex flex-col gap-2">
              <h2
                id="dimensoes-titulo"
                className="font-display text-2xl font-semibold tracking-tight text-tinta sm:text-3xl"
              >
                Quatro dimensões, uma tese
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-tinta-2">
                O motor monta a tese por camadas e fecha com síntese e
                contra-tese (bull × bear). Fato e interpretação vêm sempre
                separados no texto.
              </p>
            </div>
            <ol className="grid gap-px overflow-hidden rounded-xl border border-linha bg-linha sm:grid-cols-2">
              {DIMENSOES.map((d) => (
                <li key={d.numero} className="flex gap-4 bg-cartao p-6">
                  <span
                    aria-hidden
                    className="font-display text-2xl font-semibold text-linha-forte"
                  >
                    {d.numero}
                  </span>
                  <div className="flex flex-col gap-1.5">
                    <h3 className="text-base font-semibold text-tinta">{d.titulo}</h3>
                    <p className="text-sm leading-relaxed text-tinta-2">{d.texto}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Postura */}
        <section aria-labelledby="postura-titulo">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-14 sm:px-6">
            <h2
              id="postura-titulo"
              className="font-display text-2xl font-semibold tracking-tight text-tinta sm:text-3xl"
            >
              Auditável por construção
            </h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {PRINCIPIOS.map((p) => (
                <div
                  key={p.titulo}
                  className="flex flex-col gap-2 rounded-xl border border-linha bg-cartao p-6"
                >
                  <h3 className="font-display text-lg font-semibold text-tinta">
                    {p.titulo}
                  </h3>
                  <p className="text-sm leading-relaxed text-tinta-2">{p.texto}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-linha bg-cartao-2 px-6 py-5">
              <p className="flex-1 text-sm text-tinta-2">
                Pronto para ver como fica? Gere a tese de um ticker da B3 ou abra
                um exemplo pronto.
              </p>
              <Link
                href="/tese"
                className="rounded-lg bg-selo px-5 py-2.5 text-sm font-semibold text-sobre-selo transition-colors hover:bg-selo-forte"
              >
                Gerar tese
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer
        saudeSlot={
          <Suspense fallback={<ChipSaude />}>
            <ChipSaudeAoVivo />
          </Suspense>
        }
      />
    </>
  );
}
