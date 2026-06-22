"""Motor de tese v0 — orchestrator/workers com Anthropic Citations.

Fluxo (padrão coletar → sintetizar → riscos):
  1. Reúne fundamentos + macro (+ sinais geopolíticos, se houver) do banco.
  2. Monta documentos-fonte (um por `Fonte`) e chama o Claude com
     **Citations habilitado** → tese narrada com cada afirmação ancorada na fonte.
  3. As citações são extraídas **deterministicamente da resposta** (cada bloco de
     texto carrega `citations` → `document_index` → a `Fonte`), e não de uma 2ª
     chamada frágil. Uma etapa Haiku opcional extrai metadados (resumo/seções),
     honrando o desenho de 2 etapas (Citations é incompatível com Structured
     Outputs) sem que o núcleo dependa dela.

Regras de ouro (impostas no system prompt): nunca inventar número (abster com
"dado não encontrado"); nunca recomendar compra/venda; separar fato de
interpretação. Ver skills `tese-fundamentalista` e `extrair-dados-cvm`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Empresa, Fonte, Fundamento, MacroSerie, Tese, TeseVersao
from app.observability.langfuse_client import get_langfuse
from app.services import dados as dados_svc
from app.services.demo_user import get_or_create_demo_user

logger = get_logger(__name__)

# Preços ESTIMADOS (US$ por 1M tokens) só para telemetria de custo. Não são fato
# do produto — rotulados como estimativa. O Langfuse calcula o custo autoritativo
# pela sua própria tabela quando as chaves estão presentes.
_PRECO_ESTIMADO = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}

_SYSTEM = """\
Você é o motor de teses do "Tese AI". Monta teses de investimento ESTRUTURADAS e \
AUDITÁVEIS para ativos da B3, em português do Brasil.

REGRAS INEGOCIÁVEIS:
1. NUNCA invente número ou fato. Todo dado factual deve vir EXCLUSIVAMENTE dos \
documentos-fonte fornecidos nesta mensagem, e cada número deve estar ancorado numa \
citação à fonte. Se um dado necessário NÃO está nos documentos, escreva \
"dado não encontrado" e siga — jamais estime ou preencha.
2. NUNCA dê recomendação de compra/venda. Proibido "compre", "venda", "mantenha", \
"vale a pena", preço-alvo ou opinião direcional. Você ESTRUTURA o raciocínio; a \
decisão é do leitor (postura regulatória CVM).
3. SEPARE fato de interpretação. Marque o que é dado factual (citado) e o que é \
sua leitura/cenário ("interpretação:", "cenário:").
4. A camada geopolítica é raciocínio causal (evento→commodity→setor→empresa) e é \
INTERPRETAÇÃO: ancore-a apenas nos dados fornecidos (ex.: câmbio) e NÃO afirme \
eventos específicos (guerras, decisões da OPEP, sanções) como fato se eles não \
estiverem nos documentos — nesse caso, marque "dado não encontrado".

ESTRUTURA DA SAÍDA (markdown, exatamente estas seções):
# Tese — {TICKER} ({EMPRESA})
> Não é recomendação de investimento. Tese estruturada a partir de dados públicos.
## 1. Fundamentos
## 2. Contexto macro
## 3. Camada geopolítica (interpretação)
## 4. Síntese
## 5. Riscos e contra-tese (bull × bear)
## 6. Fontes
## 7. Lacunas
Em "Lacunas", liste explicitamente os "dado não encontrado".
"""


def _fmt_reais(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _coletar(session: Session, empresa: Empresa) -> list[tuple[Fonte, str]]:
    """Reúne (fonte, texto-do-fato) para cada dado real disponível da empresa.

    Um item por `Fonte` → vira um documento citável. Sem dado → lista vazia (e o
    chamador abstém em vez de inventar).
    """
    itens: list[tuple[Fonte, str]] = []

    fundamentos = session.execute(
        select(Fundamento)
        .where(Fundamento.empresa_id == empresa.id)
        .order_by(Fundamento.dt_refer.desc(), Fundamento.conta)
    ).scalars()
    for f in fundamentos:
        fonte = session.get(Fonte, f.fonte_id) if f.fonte_id else None
        if fonte is None or f.valor is None:
            continue
        texto = (
            f"Fundamento de {empresa.nome} ({empresa.ticker}): "
            f"{f.conta} = {_fmt_reais(float(f.valor))} "
            f"(exercício/ref. {f.dt_refer})."
        )
        itens.append((fonte, texto))

    macro = session.execute(
        select(MacroSerie).order_by(MacroSerie.codigo, MacroSerie.data.desc())
    ).scalars()
    vistos: set[str] = set()
    for m in macro:
        if m.codigo in vistos or m.valor is None:
            continue
        vistos.add(m.codigo)
        fonte = session.get(Fonte, m.fonte_id) if m.fonte_id else None
        if fonte is None:
            continue
        texto = (
            f"Indicador macro {m.codigo}: {float(m.valor)} "
            f"(referência {m.data}; {fonte.descricao})."
        )
        itens.append((fonte, texto))

    return itens


def _build_documents(itens: list[tuple[Fonte, str]]) -> tuple[list[dict], list[Fonte]]:
    """Monta os blocos `document` (Citations on) e o mapa document_index → Fonte."""
    documents: list[dict] = []
    index_to_fonte: list[Fonte] = []
    for fonte, texto in itens:
        titulo = (fonte.descricao or "fonte")[:200]
        documents.append(
            {
                "type": "document",
                "source": {"type": "text", "media_type": "text/plain", "data": texto},
                "title": titulo,
                "context": f"URL: {fonte.url or 'n/d'} | dt_referencia: {fonte.dt_referencia}",
                "citations": {"enabled": True},
            }
        )
        index_to_fonte.append(fonte)
    if documents:
        # Cacheia o prefixo (system + documentos) — estável por ticker.
        documents[-1]["cache_control"] = {"type": "ephemeral"}
    return documents, index_to_fonte


def _estimar_custo(model: str, usage) -> float | None:
    preco = _PRECO_ESTIMADO.get(model)
    if preco is None or usage is None:
        return None
    p_in, p_out = preco
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    custo = (
        inp * p_in + cache_write * p_in * 1.25 + cache_read * p_in * 0.10 + out * p_out
    ) / 1_000_000
    return round(custo, 6)


def _usage_dict(model: str, usage) -> dict:
    return {
        "modelo": model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
        "custo_estimado_usd": _estimar_custo(model, usage),
    }


def _synthesize(
    client: anthropic.Anthropic,
    model: str,
    documents: list[dict],
    index_to_fonte: list[Fonte],
    ticker: str,
    nome: str,
) -> tuple[str, list[dict], object]:
    """Chamada Opus com Citations (streaming). Devolve (markdown, citações, usage)."""
    instrucao = (
        f"Com base EXCLUSIVAMENTE nos documentos-fonte acima, monte a tese para "
        f"{ticker} ({nome}). Cite cada número à sua fonte. Onde faltar um dado, "
        f"escreva 'dado não encontrado'. Nunca recomende comprar ou vender."
    )
    content = [*documents, {"type": "text", "text": instrucao}]

    lf = get_langfuse()
    gen_cm = None
    if lf is not None:
        try:
            gen_cm = lf.start_as_current_generation(name="tese.synthesize", model=model)
            gen_cm.__enter__()
        except Exception as exc:  # pragma: no cover - tracing best-effort
            logger.warning("langfuse_gen_falhou", error_type=type(exc).__name__)
            gen_cm = None

    try:
        with client.messages.stream(
            model=model,
            max_tokens=8000,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
        ) as stream:
            final = stream.get_final_message()
    finally:
        if gen_cm is not None:
            try:
                gen_cm.__exit__(None, None, None)
            except Exception as exc:  # pragma: no cover - tracing best-effort
                logger.debug("langfuse_gen_exit_falhou", error_type=type(exc).__name__)

    partes: list[str] = []
    citacoes: list[dict] = []
    for block in final.content:
        if getattr(block, "type", None) != "text":
            continue
        partes.append(block.text)
        for c in getattr(block, "citations", None) or []:
            di = getattr(c, "document_index", None)
            fonte = (
                index_to_fonte[di]
                if isinstance(di, int) and 0 <= di < len(index_to_fonte)
                else None
            )
            citacoes.append(
                {
                    "texto_citado": getattr(c, "cited_text", None) or "",
                    "document_index": di,
                    "titulo_documento": getattr(c, "document_title", None),
                    "fonte": _fonte_dict(fonte) if fonte else None,
                }
            )
    return "".join(partes), citacoes, final.usage


def _extract_metadata_haiku(client: anthropic.Anthropic, model: str, markdown: str) -> dict | None:
    """Etapa 2 (opcional) — Haiku extrai um resumo estruturado. Não-fatal.

    Citations é incompatível com Structured Outputs, então metadados saem numa 2ª
    chamada SEM citações. Se algo falhar, a tese segue sem os metadados.
    """
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=(
                "Extraia metadados da tese a seguir. Responda APENAS um JSON com as "
                "chaves: resumo (string, 1 frase neutra, sem recomendação) e secoes "
                "(lista de títulos H2 encontrados). Nada além do JSON."
            ),
            messages=[{"role": "user", "content": markdown[:8000]}],
        )
        txt = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(txt)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("haiku_metadata_falhou", error_type=type(exc).__name__)
        return None


def _detect_lacunas(markdown: str) -> list[str]:
    """Extrai as abstenções ('dado não encontrado') que o modelo declarou."""
    lacunas: list[str] = []
    for linha in markdown.splitlines():
        if "dado não encontrado" in linha.lower():
            lacunas.append(linha.strip("-* ").strip())
    return lacunas


def _fonte_dict(fonte: Fonte) -> dict:
    return {
        "id": str(fonte.id),
        "url": fonte.url,
        "descricao": fonte.descricao,
        "dt_referencia": fonte.dt_referencia.isoformat() if fonte.dt_referencia else None,
    }


def gerar_tese(session: Session, tese_id: uuid.UUID) -> None:
    """Job de geração: lê a `Tese` (status processing), gera e persiste a versão.

    Robusto a ausência de chave/dados: nunca lança para o caller; grava o estado
    (`ready`/`error`) na própria tese. Service_role ignora RLS para gravar.
    """
    settings = get_settings()
    tese = session.get(Tese, tese_id)
    if tese is None:
        logger.warning("tese_inexistente", tese_id=str(tese_id))
        return
    ticker = tese.ticker

    try:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY ausente — configure o backend/.env para gerar.")

        empresa = dados_svc.ensure_empresa(session, ticker)
        # Garante dados reais; ingere sob demanda se a empresa ainda não tem fundamentos.
        if not session.execute(
            select(Fundamento.id).where(Fundamento.empresa_id == empresa.id).limit(1)
        ).first():
            dados_svc.ingest_fundamentos(session, empresa)
            dados_svc.ingest_macro(session)
            session.commit()

        itens = _coletar(session, empresa)
        if not itens:
            raise dados_svc.DadoNaoEncontrado(
                f"sem dados reais para {ticker} — abster (dado não encontrado)"
            )

        documents, index_to_fonte = _build_documents(itens)
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        markdown, citacoes, usage = _synthesize(
            client, settings.tese_model_synthesis, documents, index_to_fonte, ticker, empresa.nome
        )
        metadata = _extract_metadata_haiku(client, settings.tese_model_extraction, markdown)
        lacunas = _detect_lacunas(markdown)
        fontes = [_fonte_dict(f) for f in index_to_fonte]
        uso = _usage_dict(settings.tese_model_synthesis, usage)

        envelope = {
            "markdown": markdown,
            "citacoes": citacoes,
            "fontes": fontes,
            "lacunas": lacunas,
            "uso": uso,
            "metadata": metadata,
            "gerado_em": dt.datetime.now(dt.UTC).isoformat(),
        }
        prompt_hash = hashlib.sha256(
            (
                _SYSTEM + json.dumps([d.get("source") for d in documents], ensure_ascii=False)
            ).encode()
        ).hexdigest()

        versao = TeseVersao(
            tese_id=tese.id,
            user_id=tese.user_id,
            conteudo=json.dumps(envelope, ensure_ascii=False),
            modelo=settings.tese_model_synthesis,
            prompt_hash=prompt_hash,
        )
        session.add(versao)
        tese.status = "ready"
        session.commit()
        logger.info(
            "tese_gerada",
            tese_id=str(tese.id),
            ticker=ticker,
            citacoes=len(citacoes),
            lacunas=len(lacunas),
            custo_estimado_usd=uso.get("custo_estimado_usd"),
        )
    except Exception as exc:
        session.rollback()
        tese = session.get(Tese, tese_id)
        if tese is not None:
            tese.status = "error"
            session.add(
                TeseVersao(
                    tese_id=tese.id,
                    user_id=tese.user_id,
                    conteudo=json.dumps({"erro": str(exc)}, ensure_ascii=False),
                    modelo=None,
                    prompt_hash=None,
                )
            )
            session.commit()
        logger.warning(
            "tese_falhou", tese_id=str(tese_id), ticker=ticker, error_type=type(exc).__name__
        )


def criar_tese(session: Session, ticker: str) -> Tese:
    """Cria a `Tese` (status processing) com dono real (RLS). Não gera ainda."""
    user_id = get_or_create_demo_user()
    tese = Tese(user_id=uuid.UUID(user_id), ticker=ticker.upper().strip(), status="processing")
    session.add(tese)
    session.commit()
    session.refresh(tese)
    return tese
