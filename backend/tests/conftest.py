"""Fixtures compartilhadas dos testes.

Missão "A Portaria": os endpoints protegidos passam a exigir `usuario_atual`. Para os
1015 testes existentes seguirem verdes SEM editar asserção, uma identidade autenticada
PADRÃO é injetada por `dependency_overrides` (autouse). Testes que precisam de anônimo
ou de OUTRO usuário sobrepõem localmente (ver `identidade_teste`).

O perímetro `X-Portaria` fica no-op nos testes porque `PORTARIA_SECRET` não está setado
(o middleware só enforça com o segredo; o fail-closed é só em produção).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.auth import Identidade, usuario_atual
from app.main import app

IDENTIDADE_TESTE = Identidade(
    user_id="00000000-0000-0000-0000-0000000000ab",
    session_id="00000000-0000-0000-0000-0000000000cd",
    role="authenticated",
    aal="aal1",
    amr=None,
    email="teste@tese-ai.local",
    claims={},
)


@pytest.fixture(autouse=True)
def identidade_teste() -> Iterator[Identidade]:
    """Injeta a identidade autenticada padrão nas rotas com `Depends(usuario_atual)`."""
    app.dependency_overrides[usuario_atual] = lambda: IDENTIDADE_TESTE
    try:
        yield IDENTIDADE_TESTE
    finally:
        app.dependency_overrides.pop(usuario_atual, None)
