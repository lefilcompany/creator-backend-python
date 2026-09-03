# Issue 0019: synchronous text Content generation

- ADR primaria: [`0001-llm-provider`](../adr/0001-llm-provider.md)
- ADRs relacionadas: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md), [`0006-versioned-api-envelope`](../adr/0006-versioned-api-envelope.md), [`0007-openapi-first`](../adr/0007-openapi-first.md), [`0008-api-limits-and-soft-delete`](../adr/0008-api-limits-and-soft-delete.md)
- Labels: `api`, `ai`, `content`, `persistence`

## Papel

Gerar texto por IA para um Workspace autorizado, persistir o resultado como Content e devolver o artefato ao Principal autenticado no envelope versionado.

## Criterios de aceite

- `POST /api/v1/content/generate` valida `workspace_id`, `topic`, `audience`, `tone`, `content_type` e `brand_voice`.
- O prompt e montado pelo catalogo central e enviado ao provider LLM configurado.
- O resultado e persistido como Content `TEXT` com uma Generation `TEXT` vinculada.
- Erros de validacao, Workspace, provider e persistencia usam o envelope padrao.
- `GET /api/v1/content` lista o Content visivel ao mesmo usuario por Membership.
- Testes cobrem sucesso, validacao, timeout do provider, rollback e historico.
