# Issue 0040: event-driven agent pipeline

- ADR: [`0018-event-driven-agent-pipeline`](../adr/0018-event-driven-agent-pipeline.md)
- Labels: `agents`, `architecture`, `backend`

## Scope

Separar as etapas Business, Planner, Writer, Artist e Reviewer em eventos
versionados, com Outbox transacional, consumers idempotentes e Redis/RQ como
transporte inicial.

## Acceptance criteria

- [x] Evento versionado e Outbox persistente.
- [ ] Consumer independente para cada etapa.
- [ ] Persistência atômica de step + próximo evento.
- [ ] Retry, deduplicação e dead-letter queue.
- [ ] Migração do worker monolítico sem regressão da API.
