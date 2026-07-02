"""Resolução universal de ticker B3 -> CD_CVM/CNPJ/razão social/setor (keyless).

Substitui o registro manual de 4 tickers por dados públicos da CVM, generalizando
para QUALQUER companhia aberta listada:

- **FCA** (Formulário Cadastral), membro `fca_cia_aberta_valor_mobiliario_{ano}.csv`:
  mapeia o **código de negociação** (ticker/COMNEG) -> CNPJ. É a fonte de verdade
  do ticker (o `cad_cia_aberta.csv` NÃO publica ticker; a B3 não publica
  CD_CVM/CNPJ). ATENÇÃO (verificado ao vivo no layout 2026): o VM **não publica
  CD_CVM** — só `CNPJ_Companhia`.
- **CAD_CIA_ABERTA** (`cad_cia_aberta.csv`): dá o **CD_CVM** e enriquece com razão
  social, setor e situação. O JOIN VM->CAD é por **CNPJ (dígitos, chave exata)**;
  o enriquecimento interno é por `cd_cvm`. NUNCA por razão social (fuzzy match é
  fonte de alucinação — achado A2 do red-team). Linha sem join possível é
  descartada (abstém).

Formato CVM: latin-1, separador ';'. Nenhuma linha sem CD_CVM/ticker é usada
(abstém). Enquanto o cache não é populado, o `TICKER_CD_CVM` (seed) mantém os
tickers já conhecidos funcionando offline.

Escopo v1 (achados M2/M3): cobre **ações de companhias abertas**. Bancos/seguradoras
(plano de contas próprio) e FIIs (base CVM distinta) resolvem o cadastro, mas o
aprofundamento de fundamentos é roadmap — o motor abstém onde não há dado.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.models import CvmCadastro
from app.services import http_client
from app.services.dados import TICKER_CD_CVM, DadoNaoEncontrado, _parse_data
from app.services.fontes import get_or_create_fonte

logger = get_logger(__name__)

CAD_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
FCA_ZIP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
FCA_VM_MEMBRO = "fca_cia_aberta_valor_mobiliario_{ano}.csv"
# Anos a tentar para o FCA (mais recente primeiro).
_ANOS_FCA = (2026, 2025, 2024)

# Colunas-candidatas (case-insensitive) — tolerante a variações de layout da CVM.
_COL_TICKER = ("CODIGO_NEGOCIACAO", "COMNEG", "CD_NEGOCIACAO")
_COL_ESPECIE = ("VALOR_MOBILIARIO", "ESPECIE", "TP_VALOR_MOBILIARIO")
_COL_CDCVM = ("CD_CVM", "CODIGO_CVM")
_COL_CNPJ = ("CNPJ_COMPANHIA", "CNPJ_CIA")
_COL_DENOM = ("DENOM_SOCIAL", "DENOM_COMERC")
_COL_SETOR = ("SETOR_ATIV", "SETOR")
_COL_SIT = ("SIT", "SIT_REG")
_COL_DT = ("DT_REFER", "DT_REG", "DATA_REFERENCIA")
_COL_NOME_VM = ("NOME_EMPRESARIAL",)
_COL_FIM_NEG = ("DATA_FIM_NEGOCIACAO",)

# Código de negociação B3 válido: raiz de 4 alfanuméricos iniciada por letra +
# 1-2 dígitos (PETR4, B3SA3, TAEE11, AAPL34). O FCA real traz placeholders como
# "NÃO HÁ" para papéis não negociados — não são tickers e colidiriam entre
# empresas distintas no unique (comneg, especie). Verificado ao vivo em 2026-07-02.
_TICKER_B3_RE = re.compile(r"^[A-Z][A-Z0-9]{3}[0-9]{1,2}$")


def _norm(row: dict[str, str]) -> dict[str, str]:
    """Normaliza as chaves da linha para UPPER (case-insensitive lookup)."""
    return {(k or "").strip().upper(): (v or "").strip() for k, v in row.items()}


def _col(row: dict[str, str], nomes: tuple[str, ...]) -> str | None:
    for nome in nomes:
        valor = row.get(nome)
        if valor:
            return valor
    return None


def _int_cdcvm(bruto: str | None) -> int | None:
    if not bruto:
        return None
    try:
        return int(bruto.strip())
    except ValueError:
        return None


def _cnpj_digits(bruto: str | None) -> str | None:
    """CNPJ normalizado para dígitos (chave exata do JOIN VM->CAD)."""
    digitos = "".join(ch for ch in (bruto or "") if ch.isdigit())
    return digitos or None


def _ler_csv(csv_bytes: bytes) -> list[dict[str, str]]:
    """DictReader tolerante (latin-1, ';'), chaves normalizadas para UPPER."""
    texto = io.TextIOWrapper(io.BytesIO(csv_bytes), encoding="latin-1", newline="")
    return [_norm(linha) for linha in csv.DictReader(texto, delimiter=";")]


# ---------------------------------------------------------------------------
# Parsers puros
# ---------------------------------------------------------------------------
def parse_cad_cia_aberta(csv_bytes: bytes) -> dict[int, dict]:
    """CAD -> {cd_cvm: {cnpj, denom_social, setor, sit_reg}} (join key = cd_cvm)."""
    indice: dict[int, dict] = {}
    for row in _ler_csv(csv_bytes):
        cd_cvm = _int_cdcvm(_col(row, _COL_CDCVM))
        if cd_cvm is None:
            continue
        indice[cd_cvm] = {
            "cnpj": _col(row, _COL_CNPJ),
            "denom_social": _col(row, _COL_DENOM),
            "setor": _col(row, _COL_SETOR),
            "sit_reg": _col(row, _COL_SIT),
        }
    return indice


def parse_valor_mobiliario(csv_bytes: bytes) -> list[dict]:
    """FCA/VLMO valor mobiliário -> [{cd_cvm?, cnpj, comneg, especie, dt, ...}].

    `comneg` (ticker) vem SÓ daqui. O layout real 2026 NÃO traz CD_CVM (verificado
    ao vivo) — `cd_cvm` fica None e o join por CNPJ acontece no `montar`. Linhas sem
    ticker ou sem NENHUMA chave de join (cd_cvm e cnpj ausentes) são descartadas
    (abstém — nunca inventa).
    """
    linhas: list[dict] = []
    for row in _ler_csv(csv_bytes):
        cd_cvm = _int_cdcvm(_col(row, _COL_CDCVM))
        comneg = _col(row, _COL_TICKER)
        cnpj = _col(row, _COL_CNPJ)
        if not comneg or (cd_cvm is None and not cnpj):
            continue
        if not _TICKER_B3_RE.match(comneg.upper().strip()):
            continue  # placeholder ("NÃO HÁ") ou código não-B3 — não é ticker
        linhas.append(
            {
                "cd_cvm": cd_cvm,
                "cnpj": cnpj,
                "comneg": comneg.upper(),
                "especie": _col(row, _COL_ESPECIE),
                "dt_referencia": _parse_data(_col(row, _COL_DT) or ""),
                "nome_empresarial": _col(row, _COL_NOME_VM),
                "fim_negociacao": bool(_col(row, _COL_FIM_NEG)),
            }
        )
    return linhas


def montar_linhas_cadastro(vm_linhas: list[dict], cad_indice: dict[int, dict]) -> list[dict]:
    """JOIN determinístico VM->CAD. Pura.

    Chave: `cd_cvm` quando o VM o traz; senão **CNPJ em dígitos** -> CD_CVM do CAD
    (o layout 2026 do VM não publica CD_CVM). Linha sem cd_cvm resolvível é
    descartada (abstém). Saída ordenada com listagens encerradas ANTES das ativas
    e mais antigas antes das recentes — o upsert por (comneg, especie) é
    last-wins, então a listagem ativa/mais recente prevalece.
    """
    cd_por_cnpj: dict[str, int] = {}
    for cd, dados in cad_indice.items():
        digitos = _cnpj_digits(dados.get("cnpj"))
        if digitos:
            cd_por_cnpj[digitos] = cd

    ordenadas = sorted(
        vm_linhas,
        key=lambda vm: (
            0 if vm.get("fim_negociacao") else 1,
            vm.get("dt_referencia") or dt.date.min,
        ),
    )
    montadas: list[dict] = []
    for vm in ordenadas:
        cd_cvm = vm.get("cd_cvm")
        if cd_cvm is None:
            cd_cvm = cd_por_cnpj.get(_cnpj_digits(vm.get("cnpj")) or "")
        if cd_cvm is None:
            continue  # sem join possível — abstém, nunca inventa
        cad = cad_indice.get(cd_cvm, {})
        montadas.append(
            {
                "cd_cvm": cd_cvm,
                "cnpj": vm.get("cnpj") or cad.get("cnpj"),
                "denom_social": cad.get("denom_social") or vm.get("nome_empresarial") or "",
                "comneg": vm["comneg"],
                "especie": vm.get("especie"),
                "setor": cad.get("setor"),
                "sit_reg": cad.get("sit_reg"),
                "dt_referencia": vm.get("dt_referencia"),
            }
        )
    return montadas


def resolver_ticker_em_linhas(linhas: list[dict], ticker: str) -> tuple | None:
    """Resolve o ticker sobre uma lista de linhas de cadastro. Pura.

    Devolve (cd_cvm, cnpj, denom_social, setor) ou None. Multi-classe (PETR3/PETR4)
    não colide: cada COMNEG é uma linha distinta apontando ao mesmo cd_cvm.
    """
    alvo = ticker.upper().strip()
    matches = [ln for ln in linhas if (ln.get("comneg") or "").upper().strip() == alvo]
    if not matches:
        return None
    ativos = [ln for ln in matches if (ln.get("sit_reg") or "").upper().startswith("ATIV")]
    escolhido = (ativos or matches)[0]
    return (
        escolhido["cd_cvm"],
        escolhido.get("cnpj"),
        escolhido.get("denom_social") or None,
        escolhido.get("setor"),
    )


# ---------------------------------------------------------------------------
# Ingestão (IO) + resolução com fallback
# ---------------------------------------------------------------------------
def _baixar_fca_vm() -> tuple[bytes, int] | None:
    """Baixa o FCA mais recente e devolve (csv_bytes do valor_mobiliario, ano)."""
    for ano in _ANOS_FCA:
        try:
            conteudo = http_client.download_zip(FCA_ZIP_URL.format(ano=ano))
        except Exception as exc:  # rede/HTTP — tenta o ano anterior
            logger.warning("fca_falhou", ano=ano, erro=type(exc).__name__)
            continue
        membro = FCA_VM_MEMBRO.format(ano=ano)
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            if membro in z.namelist():
                return z.read(membro), ano
    return None


def ingest_cvm_cadastro(session: Session) -> int:
    """Popula `cvm_cadastro` (FCA valor_mobiliario + CAD). Bootstrap semanal.

    Idempotente por (comneg, especie). Devolve o nº de linhas gravadas/atualizadas.
    Falha de rede não explode: registra e sai (o resolve segue com o seed).
    """
    vm = _baixar_fca_vm()
    if vm is None:
        logger.warning("cvm_cadastro_sem_fca")
        return 0
    vm_bytes, ano = vm
    try:
        cad_bytes = http_client.get_keyless(CAD_URL).content
    except Exception as exc:
        logger.warning("cad_falhou", erro=type(exc).__name__)
        cad_bytes = b""

    cad_indice = parse_cad_cia_aberta(cad_bytes) if cad_bytes else {}
    vm_linhas = parse_valor_mobiliario(vm_bytes)
    montadas = montar_linhas_cadastro(vm_linhas, cad_indice)
    logger.info(
        "cvm_cadastro_join",
        ano=ano,
        vm_linhas=len(vm_linhas),
        cad_empresas=len(cad_indice),
        montadas=len(montadas),
    )
    if vm_linhas and not montadas:
        # VM sem CD_CVM (layout 2026) + CAD indisponível => nenhum join possível.
        logger.warning("cvm_cadastro_join_vazio", ano=ano, cad_disponivel=bool(cad_indice))

    fonte_id = get_or_create_fonte(
        session,
        url=FCA_ZIP_URL.format(ano=ano),
        descricao=f"CVM FCA {ano} — valores mobiliários (ticker↔CD_CVM) + CAD_CIA_ABERTA",
        dt_referencia=dt.date(ano, 12, 31),
    )
    # Dedup em memória por (comneg, especie), last-wins (montar já ordena com a
    # listagem ativa/mais recente por último). Necessário: a sessão tem
    # autoflush=False, então duplicatas pendentes não seriam vistas pelo SELECT
    # e estourariam o unique no commit (verificado ao vivo em 2026-07-02).
    dedup: dict[tuple[str, str | None], dict] = {(m["comneg"], m["especie"]): m for m in montadas}
    existentes: dict[tuple[str, str | None], CvmCadastro] = {
        (obj.comneg, obj.especie): obj
        for obj in session.execute(select(CvmCadastro)).scalars()
        if obj.comneg is not None
    }
    gravados = 0
    for chave, m in dedup.items():
        existente = existentes.get(chave)
        if existente is None:
            session.add(CvmCadastro(fonte_id=fonte_id, **m))
        else:
            for campo, valor in m.items():
                setattr(existente, campo, valor)
            existente.fonte_id = fonte_id
        gravados += 1
    logger.info("cvm_cadastro_persistido", ano=ano, linhas=gravados)
    return gravados


def _obj_para_linha(obj: CvmCadastro) -> dict:
    return {
        "cd_cvm": obj.cd_cvm,
        "cnpj": obj.cnpj,
        "denom_social": obj.denom_social,
        "comneg": obj.comneg,
        "especie": obj.especie,
        "setor": obj.setor,
        "sit_reg": obj.sit_reg,
    }


def resolve_ticker(session: Session | None, ticker: str) -> tuple[int, str | None, str, str | None]:
    """ticker B3 -> (cd_cvm, cnpj, denom_social, setor). Abstém se desconhecido.

    Ordem: (1) cache `cvm_cadastro` (qualquer empresa listada); (2) seed
    `TICKER_CD_CVM` (offline, enquanto o cache não foi populado). `session=None`
    pula o cache (usado nos testes de abstenção sem tocar no banco).
    """
    alvo = ticker.upper().strip()
    linhas: list[dict] = []
    if session is not None:
        objs = (
            session.execute(
                select(CvmCadastro)
                .where(CvmCadastro.comneg == alvo)
                .order_by(CvmCadastro.dt_referencia.desc().nullslast())
            )
            .scalars()
            .all()
        )
        linhas = [_obj_para_linha(o) for o in objs]

    hit = resolver_ticker_em_linhas(linhas, alvo)
    if hit is not None:
        return hit

    seed = TICKER_CD_CVM.get(alvo)
    if seed is not None:
        cd_cvm, nome, setor = seed
        return (cd_cvm, None, nome, setor)

    raise DadoNaoEncontrado(f"ticker {alvo} não encontrado no cadastro CVM (dado não encontrado)")
