# Issue 0020: core resource CRUD

- ADR primaria: [`0011-core-resource-crud`](../adr/0011-core-resource-crud.md)
- ADRs relacionadas: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md), [`0006-versioned-api-envelope`](../adr/0006-versioned-api-envelope.md), [`0007-openapi-first`](../adr/0007-openapi-first.md), [`0008-api-limits-and-soft-delete`](../adr/0008-api-limits-and-soft-delete.md)
- Labels: `api`, `persistence`, `workspace`, `crud`

## Papel

Criar as tabelas e APIs CRUD para Brand, Project, Content, Generation, Asset e Brand Settings, preservando Users e Workspaces existentes.

## Criterios de aceite

- Alembic cria `brands`, `projects`, `assets`, `brand_settings` e adiciona `brand_id`/`project_id` opcionais em Content e Generation.
- Repositórios e Unit of Work expõem CRUD escopado por Workspace.
- Rotas REST protegidas retornam envelope versionado e aplicam Membership para leitura e escrita.
- `users` tem CRUD administrativo e `/api/v1/users/me`.
- Fluxos existentes de geracao de texto e imagem continuam funcionando.
- Testes cobrem API, repositórios, modelos e regressões existentes.
