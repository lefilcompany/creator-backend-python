# Issue 0029: activity events timeline

- ADR primária: [`0010-architecture-governance`](../adr/0010-architecture-governance.md)
- ADR tracker: [#43](https://github.com/lefilcompany/creator-backend-python/issues/43)
- GitHub: [#52](https://github.com/lefilcompany/creator-backend-python/issues/52)
- Labels: `backend`, `database`, `architecture`, `adr-010`

## Contexto

O produto precisa de histórico operacional, auditoria e timeline por Workspace. O `activity_log` do legado não deve ser replicado nem misturado com observabilidade técnica.

## Objetivo

Criar eventos de negócio append-oriented para consultas por Workspace, usuário, Brand e entidade, com `entity_type/entity_id` explicitamente polimórficos.

## Modelo esperado

- `activity_events`: `id`, `workspace_id`, `user_id` nullable, `brand_id` nullable, `entity_type`, `entity_id` nullable, `event_type`, `metadata`, `created_at`.
- Definir catálogo de `event_type`, limites de `entity_type`, retenção, imutabilidade e redaction de metadata sensível.
- Validar ownership da entidade na criação mesmo sem FK direta para `entity_id`.
- Indexar `(workspace_id, created_at)`, usuário, Brand e `(entity_type, entity_id)`.

## Critérios de aceite

- [ ] Migration Alembic reversível e modelo SQLAlchemy implementados.
- [ ] Eventos sempre respeitam autorização e isolamento de Workspace.
- [ ] Timeline tem paginação estável e ordenação determinística.
- [ ] Testes cobrem Workspace, usuário, Brand, entidade e isolamento.
- [ ] Não replica `activity_log` nem grava secrets/tokens.
- [ ] Decisão material de retenção/auditoria atualiza ADR antes do código.

## Dependências

- Depends on: `workspaces`, `workspace_memberships`, `users`, `brands`.
- Related: ADR-005, ADR-006, ADR-007, ADR-008, ADR-010; issue #28.
