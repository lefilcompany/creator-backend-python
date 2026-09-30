# [FASE 3][AI] Generation Job por tipo de artefato

- ADR primária: [ADR-016](../adr/0016-polymorphic-generation-job-artifacts.md)
- Relacionadas: ADR-003, ADR-014, #56, #58 e #66

## Escopo

Adicionar contratos provider-neutral e persistência explícita para imagem, copy
e legenda, preservando isolamento por Workspace, ownership, request_id e soft delete.

## Checklist

- [x] Contratos e política de execução no domínio
- [x] Campos de job/evento e migration
- [x] OpenAPI atualizado antes da API
- [ ] Workers e endpoints polimórficos
- [ ] Testes de integração dos três tipos e reprocessamento
