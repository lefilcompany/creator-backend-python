# ADR-015: Alinhamento incremental ao diagrama Creator DB

- Status: accepted
- Fonte: `Creator DB.pdf` fornecido para esta mudança
- Tracker: [docs/issues/0037](../issues/0037-database-diagram-alignment.md)

## Contexto

O diagrama de banco inclui os domínios de workspace, billing, assinaturas,
notificações, campanhas, planejamento e geração. O código atual implementa apenas
parte desse modelo, principalmente o núcleo de geração e seus fluxos assíncronos.

## Decisão

O diagrama é a referência do schema-alvo. A migração será feita por fatias de
domínio, mantendo compatibilidade dos fluxos existentes e sem remover tabelas
ativas antes de haver models, DTOs, migrations, contratos OpenAPI e testes
correspondentes. DTOs HTTP ficam agrupados por contexto em `creator.api.dtos`.

## Consequências

O primeiro incremento reorganiza os DTOs de entrada sem alterar o contrato
externo. A implementação das tabelas adicionais deve seguir em issues separadas,
com isolamento por Workspace e migrations Alembic reversíveis.

## Issues vinculadas

Consulte [docs/issues/0037](../issues/0037-database-diagram-alignment.md) e o
[tracker central](../ADR-ISSUE-TRACKER.md).
