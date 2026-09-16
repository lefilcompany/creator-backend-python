# Issue 0032: specialist-agent image generation workflow

- ADR primária: [`0014-agent-image-generation-workflow`](../adr/0014-agent-image-generation-workflow.md)
- ADRs relacionadas: [`0001-llm-provider`](../adr/0001-llm-provider.md), [`0003-async-image-generation`](../adr/0003-async-image-generation.md), [`0011-crewai-multi-agent-orchestration`](../adr/0011-crewai-multi-agent-orchestration.md), [`0012-langchain-rag-tool-calling`](../adr/0012-langchain-rag-tool-calling.md)
- ADR tracker: [#56](https://github.com/lefilcompany/creator-backend-python/issues/56)
- GitHub: [#56](https://github.com/lefilcompany/creator-backend-python/issues/56)
- Labels: `architecture`, `agents`, `backend`, `priority-high`, `adr-014`

## Goal

Implementar o workflow assíncrono `Business → Planner → Writer → Artist → Reviewer`, com persistência por etapa, revisão multimodal, refação limitada e aprovação humana opcional.

## Acceptance criteria

- [x] OpenAPI define o endpoint de workflow e seus schemas antes da alteração de comportamento.
- [x] Máquina de estados valida transições e limita refações.
- [x] Workspace é derivado da Brand autorizada e todos os outputs são auditáveis.
- [x] Geração direta existente permanece compatível.
- [x] Migration, testes de integração e `make check` concluídos.

## Linked implementation issues

- [`0033-agent-workflow-persistence`](0033-agent-workflow-persistence.md)
- [`0034-specialist-agent-contracts`](0034-specialist-agent-contracts.md)
- [`0035-multimodal-image-reviewer`](0035-multimodal-image-reviewer.md)
- [`0036-agent-workflow-api-worker`](0036-agent-workflow-api-worker.md)

GitHub implementation issues: [#57](https://github.com/lefilcompany/creator-backend-python/issues/57), [#58](https://github.com/lefilcompany/creator-backend-python/issues/58), [#59](https://github.com/lefilcompany/creator-backend-python/issues/59), [#60](https://github.com/lefilcompany/creator-backend-python/issues/60).
