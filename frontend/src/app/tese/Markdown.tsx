// Renderizador de markdown MÍNIMO e SEGURO (sem biblioteca — restrição do projeto).
// Não usa dangerouslySetInnerHTML: cada linha vira um nó React, eliminando o risco
// de injeção de HTML vindo da saída do LLM (ver AGENTS.md: "saída do LLM ... sem sanitizar").
// Suporta: # / ## / ### títulos, listas (-, *, 1.), e parágrafos. Negrito **inline**.

import { Fragment, type ReactNode } from "react";

type Block =
  | { kind: "h1" | "h2" | "h3" | "p"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] };

function parse(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];

  let paragraph: string[] = [];
  let list: { type: "ul" | "ol"; items: string[] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: "p", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push({ kind: list.type, items: list.items });
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const trimmed = line.trim();

    if (trimmed === "") {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = /^(#{1,3})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      blocks.push({
        kind: level === 1 ? "h1" : level === 2 ? "h2" : "h3",
        text: heading[2].trim(),
      });
      continue;
    }

    const unordered = /^[-*]\s+(.*)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(unordered[1].trim());
      continue;
    }

    const ordered = /^\d+[.)]\s+(.*)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(ordered[1].trim());
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  return blocks;
}

// Negrito **texto** -> <strong>. Sem HTML cru; só nós React.
function renderInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const bold = /^\*\*([^*]+)\*\*$/.exec(part);
    if (bold) {
      return <strong key={i}>{bold[1]}</strong>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function Markdown({ source }: { source: string }) {
  const blocks = parse(source);

  return (
    <div className="flex flex-col gap-4 text-neutral-800 dark:text-neutral-200">
      {blocks.map((block, i) => {
        switch (block.kind) {
          case "h1":
            return (
              <h2
                key={i}
                className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100"
              >
                {renderInline(block.text)}
              </h2>
            );
          case "h2":
            return (
              <h3
                key={i}
                className="mt-2 text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100"
              >
                {renderInline(block.text)}
              </h3>
            );
          case "h3":
            return (
              <h4
                key={i}
                className="mt-1 text-base font-semibold text-neutral-900 dark:text-neutral-100"
              >
                {renderInline(block.text)}
              </h4>
            );
          case "ul":
            return (
              <ul
                key={i}
                className="list-disc space-y-1 pl-5 text-sm leading-relaxed"
              >
                {block.items.map((item, j) => (
                  <li key={j}>{renderInline(item)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol
                key={i}
                className="list-decimal space-y-1 pl-5 text-sm leading-relaxed"
              >
                {block.items.map((item, j) => (
                  <li key={j}>{renderInline(item)}</li>
                ))}
              </ol>
            );
          case "p":
          default:
            return (
              <p key={i} className="text-sm leading-relaxed">
                {renderInline(block.text)}
              </p>
            );
        }
      })}
    </div>
  );
}
