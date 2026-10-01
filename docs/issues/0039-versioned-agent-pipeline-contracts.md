# Issue 0039: versioned agent pipeline contracts

- ADR: [`0017-versioned-agent-pipeline-contracts`](../adr/0017-versioned-agent-pipeline-contracts.md)
- Labels: `agents`, `architecture`, `implementation`

## Scope

Garantir que cada etapa consuma somente o output validado da etapa anterior, com
provenance, hashes, refinamento estruturado e auditoria de lineage.

## Acceptance criteria

- [x] Edges versionados e validação de Workspace/schema.
- [x] Envelopes estruturados sem hidden reasoning.
- [x] Feedback de Reviewer preserva origem e precedência.
- [x] Auditoria registra hashes, schema, predecessor e correlation.
- [x] Testes cobrem handoff, mismatch e isolamento.
