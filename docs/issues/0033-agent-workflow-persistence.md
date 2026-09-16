# Issue 0033: agent workflow persistence and state machine

- ADR: [`0014-agent-image-generation-workflow`](../adr/0014-agent-image-generation-workflow.md)
- Labels: `architecture`, `database`, `backend`, `implementation`
- GitHub: [#57](https://github.com/lefilcompany/creator-backend-python/issues/57)

## Scope

Persistir `AgentWorkflowRun` e `AgentWorkflowStep`, seus estados, decisões, prompts, outputs validados, erros sanitizados, tentativas e imagens finais, com isolamento composto por Workspace.

## Acceptance criteria

- [x] Migration Alembic reversível, modelos, repositories e Unit of Work.
- [x] Transições válidas e inválidas cobertas por testes.
- [x] Idempotência por Workspace e chave de request.
- [x] UTC, soft delete e locks para retomada segura.
