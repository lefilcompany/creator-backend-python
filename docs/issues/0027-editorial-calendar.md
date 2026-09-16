# Issue 0027: editorial calendar entities

- ADR primária: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md)
- ADR relacionada: [`0011-core-resource-crud`](../adr/0011-core-resource-crud.md)
- ADR tracker: [#38](https://github.com/lefilcompany/creator-backend-python/issues/38)
- GitHub: [#50](https://github.com/lefilcompany/creator-backend-python/issues/50)
- Labels: `backend`, `database`, `architecture`, `priority-high`, `adr-005`

## Contexto

Brand, Project e Content já existem, mas não há domínio explícito de planejamento editorial. Um JSON genérico não oferece consultas, estados, datas ou vínculos seguros com Content.

## Objetivo

Criar calendários editoriais por Brand e Workspace, permitindo que itens planejados evoluam para Content e publicação futura.

## Modelo esperado

- `calendars`: `id`, `workspace_id`, `brand_id`, `name`, `description`, `created_by_user_id`, `created_at`, `updated_at`; avaliar `deleted_at`.
- `calendar_items`: `id`, `calendar_id`, `workspace_id`, `brand_id`, `content_id` nullable, `title`, `briefing`, `scheduled_date`, `status`, `metadata`, `created_at`, `updated_at`; avaliar `deleted_at`.
- Definir status controlado para planejamento, criação, revisão, aprovação, publicação e cancelamento.
- Garantir por FK composta ou restrição equivalente que Calendar, Item, Brand e Content pertençam ao mesmo Workspace/Brand.
- Indexar `(workspace_id, brand_id, scheduled_date)`, status e calendário.

## Critérios de aceite

- [ ] Migration Alembic reversível e modelos SQLAlchemy implementados.
- [ ] `content_id` opcional permite planejar antes da criação e associar depois.
- [ ] Status, datas UTC, metadata e Soft Delete estão documentados e testados.
- [ ] Testes cobrem transições, referências cross-Workspace e listagens.
- [ ] Se houver API, `docs/openapi.yaml` é atualizado antes da implementação.

## Dependências

- Depends on: `workspaces`, `workspace_memberships`, `brands`, `contents`.
- Related: ADR-005, ADR-007, ADR-008, ADR-011; issue local 0020.
