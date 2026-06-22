"""Gera 1 tese real ponta-a-ponta e roda o gate de avaliação. Imprime o laudo.

Uso (com .env contendo ANTHROPIC_API_KEY + DATABASE_URL):
    .venv/Scripts/python.exe -m app.scripts.gerar_e_avaliar PETR4

Faz: cria a tese (dono real via demo_user) -> gera (CVM/BCB + Citations, síncrono)
-> lê o envelope persistido -> avalia (sem-recomendação / citações / abstenção).
Sai com código 1 se o gate reprovar.
"""

from __future__ import annotations

import json
import sys

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.models import TeseVersao
from app.services.avaliacao import avaliar_tese
from app.services.tese import criar_tese, gerar_tese

logger = get_logger(__name__)


def main(ticker: str) -> int:
    configure_logging("development")
    if SessionLocal is None:
        print("ERRO: DATABASE_URL ausente (.env).")
        return 2

    session = SessionLocal()
    try:
        tese = criar_tese(session, ticker)
        print(f"tese criada: {tese.id} (status={tese.status}) — gerando...")
        gerar_tese(session, tese.id)
        session.expire_all()

        versao = (
            session.query(TeseVersao)
            .filter(TeseVersao.tese_id == tese.id)
            .order_by(TeseVersao.criado_em.desc())
            .first()
        )
        if versao is None or not versao.conteudo:
            print("ERRO: nenhuma versão persistida.")
            return 2
        envelope = json.loads(versao.conteudo)
        if envelope.get("erro"):
            print(f"GERAÇÃO FALHOU: {envelope['erro']}")
            return 1

        laudo = avaliar_tese(envelope)
        print("\n=== TESE (markdown) ===\n")
        print(envelope.get("markdown", "")[:4000])
        print("\n=== LAUDO DE AVALIAÇÃO ===")
        print(json.dumps(laudo, ensure_ascii=False, indent=2))
        print(f"\nuso: {json.dumps(envelope.get('uso'), ensure_ascii=False)}")
        return 0 if laudo["aprovado"] else 1
    finally:
        session.close()


if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else "PETR4"
    raise SystemExit(main(alvo))
