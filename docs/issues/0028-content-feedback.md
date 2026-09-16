# Issue 0028: content feedback system

- ADR primária: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md)
- ADR relacionada: [`0011-core-resource-crud`](../adr/0011-core-resource-crud.md)
- ADR tracker: [#38](https://github.com/lefilcompany/creator-backend-python/issues/38)
- GitHub: [#51](https://github.com/lefilcompany/creator-backend-python/issues/51)
- Labels: `backend`, `database`, `architecture`, `adr-005`

## Contexto

Content e Generation já são persistidos, mas a avaliação humana não é registrada. Isso impede uma base auditável para melhoria de prompts, ranking e aprendizado futuro.

## Objetivo

Persistir feedback de um Principal sobre Content, com correlação opcional à Generation que produziu ou transformou o artefato.

## Modelo esperado

- `content_feedback`: `id`, `workspace_id`, `user_id`, `content_id`, `generation_id` nullable, `feedback_type`, `rating` nullable, `metadata`, `created_at`.
- Controlar vocabulário de `feedback_type` e limites de `rating`.
- Garantir por FKs compostas ou checagens equivalentes que Content e Generation pertençam ao mesmo Workspace.
- Indexar por Workspace/Content, Generation, usuário e data; definir política para múltiplos feedbacks, correções e revogações.

## Critérios de aceite

- [ ] Migration Alembic reversível e modelo SQLAlchemy implementados.
- [ ] Relacionamentos impedem mistura de tenants.
- [ ] Tipos e rating são validados no boundary e no banco quando possível.
- [ ] Política de imutabilidade, correção e Soft Delete é documentada.
- [ ] Testes cobrem feedback por Content/Generation, rating inválido e isolamento.
- [ ] Se houver API, `docs/openapi.yaml` é atualizado antes da implementação.

## Dependências

- Depends on: `users`, `workspaces`, `contents`, `generations`.
- Related: ADR-005, ADR-007, ADR-008, ADR-011; issues #18 e #19.
