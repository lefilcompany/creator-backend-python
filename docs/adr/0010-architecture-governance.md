# ADR-010: Governança de decisões e issues

- Status: accepted
- Fonte: decisão de bootstrap do repositório
- Tracker: [#43](https://github.com/lefilcompany/creator-backend-python/issues/43)

## Contexto

O projeto será desenvolvido com engenharia agêntica e precisa manter decisões explicáveis e trabalho rastreável.

## Decisão

Toda decisão arquitetural material deve ter ADR, issue versionada e, quando possível, issue remota no GitHub. O `AGENTS.md` define o fluxo e o script de sincronização é idempotente.

## Consequências

Há uma fonte auditável no repositório mesmo quando GitHub estiver indisponível. A publicação remota exige credencial válida e não bloqueia o desenvolvimento local.

## Issues vinculadas

#1, #21, #26, #30, #31 e #44. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
