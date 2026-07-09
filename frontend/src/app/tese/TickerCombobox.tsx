"use client";

// Combobox de ticker com sugestões da lista embutida (src/lib/tickers.ts —
// carteira IBOV, fonte B3 datada). Padrão ARIA combobox/listbox com navegação
// por teclado. A lista é conveniência: ticker fora dela segue permitido, desde
// que passe no formato B3 (validação espelhada do backend).

import { useEffect, useId, useRef, useState } from "react";

import { buscarPapeis, DATA_CARTEIRA_IBOV, papelPorTicker, type PapelB3 } from "@/lib/tickers";

type Props = {
  value: string;
  onChange: (valor: string) => void;
  disabled?: boolean;
  inputId: string;
};

function formatPct(pct: number): string {
  return pct.toLocaleString("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function formatDataIso(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

export function TickerCombobox({ value, onChange, disabled, inputId }: Props) {
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const raizRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  const sugestoes: PapelB3[] = aberto ? buscarPapeis(value, 8) : [];
  const exato = papelPorTicker(value);

  // Fecha ao clicar/tocar fora (pointerdown cobre mouse e toque).
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: PointerEvent) => {
      if (!raizRef.current?.contains(e.target as Node)) {
        setAberto(false);
        setAtivo(-1);
      }
    };
    document.addEventListener("pointerdown", fechar);
    return () => document.removeEventListener("pointerdown", fechar);
  }, [aberto]);

  const selecionar = (papel: PapelB3) => {
    onChange(papel.ticker);
    setAberto(false);
    setAtivo(-1);
  };

  // Mantém a opção ativa visível quando a lista rola (teclado).
  const idAtivo =
    aberto && ativo >= 0 && sugestoes[ativo]
      ? `${listboxId}-${sugestoes[ativo].ticker}`
      : undefined;
  useEffect(() => {
    if (!idAtivo) return;
    document.getElementById(idAtivo)?.scrollIntoView({ block: "nearest" });
  }, [idAtivo]);

  const aoTeclar = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!aberto) setAberto(true);
      setAtivo((a) => Math.min(a + 1, sugestoes.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!aberto) {
        setAberto(true); // ArrowUp também abre (padrão ARIA combobox)
        return;
      }
      setAtivo((a) => Math.max(a - 1, 0));
      return;
    }
    if (e.key === "Enter" && aberto && ativo >= 0 && sugestoes[ativo]) {
      e.preventDefault(); // Enter com opção ativa seleciona; sem opção, submete
      selecionar(sugestoes[ativo]);
      return;
    }
    if (e.key === "Escape") {
      setAberto(false);
      setAtivo(-1);
    }
  };

  return (
    <div ref={raizRef} className="relative">
      <input
        id={inputId}
        name="ticker"
        role="combobox"
        aria-expanded={aberto && sugestoes.length > 0}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={idAtivo}
        value={value}
        onChange={(e) => {
          onChange(e.target.value.toUpperCase());
          setAberto(true);
          setAtivo(-1);
        }}
        onKeyDown={aoTeclar}
        onFocus={() => setAberto(true)}
        placeholder="PETR4"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        aria-describedby={`${inputId}-hint`}
        className="min-h-11 w-full border border-field bg-card px-3 py-2.5 font-mono text-ui text-ink outline-none placeholder:text-ink-3 focus:border-brasa-texto disabled:opacity-60"
      />
      <span id={`${inputId}-hint`} className="mt-1.5 block text-label text-ink-3">
        {exato ? (
          <>
            {exato.nome} ·{" "}
            <span className="font-mono text-ink-3">{formatPct(exato.participacaoPct)}%</span> da
            carteira IBOV ({formatDataIso(DATA_CARTEIRA_IBOV)})
          </>
        ) : (
          "Código de negociação da B3 — ex.: PETR4, VALE3, ITUB4."
        )}
      </span>

      {aberto && sugestoes.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Sugestões de ticker"
          className="sombra-elevada absolute left-0 right-0 top-full z-30 mt-1 max-h-72 overflow-y-auto border border-line-strong bg-elevated py-1"
        >
          {sugestoes.map((papel, i) => (
            <li
              key={papel.ticker}
              id={`${listboxId}-${papel.ticker}`}
              role="option"
              aria-selected={i === ativo}
              // pointerdown antes do blur do input — evita a corrida clique×fechar
              onPointerDown={(e) => {
                e.preventDefault();
                selecionar(papel);
              }}
              onPointerMove={() => setAtivo(i)}
              className={`flex min-h-11 cursor-pointer items-baseline justify-between gap-3 px-3 py-2 text-ui ${
                i === ativo ? "bg-realce" : ""
              }`}
            >
              <span className="font-mono font-semibold text-ink">{papel.ticker}</span>
              <span className="min-w-0 flex-1 truncate text-right text-ink-2">{papel.nome}</span>
              <span className="font-mono text-meta text-ink-3">{formatPct(papel.participacaoPct)}%</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
