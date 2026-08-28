# Issue 0012: repositories and Unit of Work

- ADR primária: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md)
- ADRs relacionadas: [`0003-async-image-generation`](../adr/0003-async-image-generation.md), [`0008-api-limits-and-soft-delete`](../adr/0008-api-limits-and-soft-delete.md)
- Labels: `database`, `architecture`, `jobs`

## Papel

Isolar acesso ao banco por repositórios substituíveis e delimitar transações dos casos de uso com Unit of Work.

## Critérios de aceite

- Serviços não acessam `Session` SQLAlchemy diretamente.
- Commit e rollback têm comportamento testado.
- Consultas de histórico aceitam filtros e ordenação definidos.
- Consultas principais permanecem escopadas por usuário, Workspace e Content quando aplicável.
- Claim de Generation Job faz transição atômica de `PENDING` para `PROCESSING`.
