# Tracker de ADRs e Issues

Este arquivo é o índice versionado da relação entre decisões arquiteturais e trabalho de implementação. Uma ADR registra uma decisão; ela pode ter várias issues. Uma issue tem uma ADR primária e pode referenciar ADRs relacionadas.

As issues #34 a #43 são issues de acompanhamento - não são tarefas duplicadas. As tarefas executáveis permanecem em #2 a #33. A issue #44 controla a descoberta e a migração do legado.

| ADR | Issue tracker | Issues de implementação |
| --- | --- | --- |
| [ADR-001](adr/0001-llm-provider.md) | [#34](https://github.com/lefilcompany/creator-backend-python/issues/34) | #3, #9, #11, #13, [#17](issues/0017-prompt-templates.md), [#19](issues/0019-sync-text-content-generation.md), #23, #27 |
| [ADR-002](adr/0002-image-storage.md) | [#35](https://github.com/lefilcompany/creator-backend-python/issues/35) | #3, #5, #10, #16, #33 |
| [ADR-003](adr/0003-async-image-generation.md) | [#36](https://github.com/lefilcompany/creator-backend-python/issues/36) | #3, #5, #7, #8, #12, #13, #16, #25, #33 |
| [ADR-004](adr/0004-supabase-auth.md) | [#37](https://github.com/lefilcompany/creator-backend-python/issues/37) | #3, #14, #15, #20, #25 |
| [ADR-005](adr/0005-postgresql-sqlalchemy-alembic.md) | [#38](https://github.com/lefilcompany/creator-backend-python/issues/38) | #2, #3, #5, #6, #12, [#19](issues/0019-sync-text-content-generation.md), #29 |
| [ADR-006](adr/0006-versioned-api-envelope.md) | [#39](https://github.com/lefilcompany/creator-backend-python/issues/39) | #4, #13, #16, #17, #18, [#19](issues/0019-sync-text-content-generation.md), #25, #28 |
| [ADR-007](adr/0007-openapi-first.md) | [#40](https://github.com/lefilcompany/creator-backend-python/issues/40) | #4, #13, #16, #17, #18, [#19](issues/0019-sync-text-content-generation.md), #25, #30, #31 |
| [ADR-008](adr/0008-api-limits-and-soft-delete.md) | [#41](https://github.com/lefilcompany/creator-backend-python/issues/41) | #5, #13, #15, #18, [#19](issues/0019-sync-text-content-generation.md), #22, #25 |
| [ADR-009](adr/0009-cloud-run-deployment.md) | [#42](https://github.com/lefilcompany/creator-backend-python/issues/42) | #3, #7, #24, #30, #31, #32 |
| [ADR-010](adr/0010-architecture-governance.md) | [#43](https://github.com/lefilcompany/creator-backend-python/issues/43) | #1, #21, #26, #30, #31, #44 |

## Regras de atualização

1. Abra uma ADR antes de iniciar trabalho que altere uma decisão arquitetural material.
2. Vincule toda issue à ADR primária no corpo e à issue tracker da ADR pelo GitHub.
3. Não feche a issue tracker enquanto houver issues de implementação abertas; atualize o checklist de progresso.
4. Uma nova necessidade de implementação entra na ADR existente quando preserva a decisão. Crie uma nova ADR apenas quando a decisão ou seus trade-offs mudarem.
5. Na implementação, PRs devem usar `Refs #<issue>`; somente critérios de aceite satisfeitos permitem `Closes #<issue>`.
