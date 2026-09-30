# ADR-016: Generation Job polimórfico por tipo de artefato

- Status: accepted
- Relacionada: ADR-003 e ADR-014
- Tracker: `docs/issues/0038-polymorphic-generation-job-artifacts.md`

## Decisão

Generation Job é a fronteira assíncrona comum, provider-neutral, e identifica
`artifact_type` (`IMAGE`, `COPY`, `CAPTION`) e `operation`. Inputs e outputs
continuam contratos específicos: texto é conteúdo limitado e versionado; imagem
é referência a objeto armazenado com metadados, nunca bytes em eventos.
Política de retry, timeout, idempotência e falha fica no job por execução.
Eventos são append-only e carregam tipo, versão, correlação, request_id e apenas
resultado sanitizado.

## Consequências

O fluxo legado de imagem permanece compatível (`IMAGE` é o default de migração),
enquanto copy e legenda não precisam fingir que são arquivos. Novos providers
implementam contratos por tipo atrás das interfaces da aplicação.

## Issues vinculadas

- Tracker: `docs/issues/0038-polymorphic-generation-job-artifacts.md`.
- Complementa #56, #58 e #66.
