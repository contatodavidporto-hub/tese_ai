# Política de Segurança — Tese AI

## Versões suportadas
Só a versão em produção (`master`) recebe correções de segurança. Não há releases antigas mantidas.

## Como relatar uma vulnerabilidade (divulgação responsável)
Encontrou uma falha? **Não abra issue pública nem divulgue antes da correção.**

- **Contato:** `contato.davidporto@gmail.com` (assunto começando com `SECURITY:`).
- Inclua: passos de reprodução, impacto, e — se possível — uma PoC mínima. Não exfiltre dados de
  terceiros nem degrade o serviço para demonstrar.
- **Resposta:** confirmamos o recebimento em até **3 dias úteis** e damos um prazo de correção
  conforme a severidade (SEV-1 imediato; ver `docs/security/plano-resposta-incidentes-lgpd.md`).

## Escopo
**Em escopo:** o frontend de produção (Vercel), o backend de produção (Railway) e a API pública deste
repositório. **Fora de escopo:** os provedores terceiros que apenas hospedam/servem o sistema (Vercel,
Railway, Supabase, Anthropic, GitHub) e os provedores de dados públicos consumidos (CVM, SEC, BCB, B3,
ANEEL, ANBIMA, FRED, World Bank) — reporte falhas deles diretamente a eles.

## Regras para testes de segurança
Testes são bem-vindos **desde que**:
- Só contra **o nosso** sistema, nunca contra terceiros.
- **Não degradem produção** — nada de DoS, fuzzing agressivo ou esgotamento de custo de LLM em produção.
  Para testes intrusivos, peça um ambiente de preview.
- Sem engenharia social, sem acesso físico, sem ataque a contas de outras pessoas.
- Respeite a LGPD: se topar com dado pessoal, pare e reporte — não copie nem retenha.

## Safe harbor
Pesquisa de boa-fé que siga esta política não será tratada como violação de acesso; agiremos de boa-fé de
volta. Não há programa de recompensa (bug bounty) monetário no momento — crédito público mediante acordo.

## Postura do produto
Este é um sistema **fintech de estruturação de teses** (não dá recomendação de compra/venda — postura CVM) e
opera sob **zero alucinação** (todo dado com fonte). Falhas que quebrem essas garantias (ex.: fazer o modelo
recomendar, ou emitir dado sem fonte) são tratadas como **vulnerabilidades de segurança do produto**.
