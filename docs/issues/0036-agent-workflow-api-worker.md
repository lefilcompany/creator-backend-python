# Issue 0036: agent workflow API and worker

- ADR: [`0014-agent-image-generation-workflow`](../adr/0014-agent-image-generation-workflow.md)
- Labels: `backend`, `api`, `implementation`
- GitHub: [#60](https://github.com/lefilcompany/creator-backend-python/issues/60)

## Scope

Implementar os endpoints de criação, status, etapas e decisão humana, o enqueue RQ e o worker assíncrono, preservando os endpoints diretos existentes.

## Acceptance criteria

- [x] Endpoints estão agrupados sob a tag Swagger `Generations`.
- [x] POST retorna 202, respeita Idempotency-Key e não aceita Workspace não autorizado.
- [x] Aprovação, refação e rejeição humana respeitam o estado atual.
- [x] Testes de contrato OpenAPI, API, worker, retomada e regressão passam.
