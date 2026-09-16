# Issue 0031: credits wallet and transactions

- ADR primária: [`0005-postgresql-sqlalchemy-alembic`](../adr/0005-postgresql-sqlalchemy-alembic.md)
- ADR relacionada: [`0001-llm-provider`](../adr/0001-llm-provider.md)
- ADR tracker: [#38](https://github.com/lefilcompany/creator-backend-python/issues/38)
- GitHub: [#54](https://github.com/lefilcompany/creator-backend-python/issues/54)
- Labels: `backend`, `database`, `architecture`, `priority-high`, `adr-005`

## Contexto

Creator precisa controlar saldo e consumo por Workspace para gerações de imagem, texto, melhorias e futuros agentes. A issue #23 cobre tokens/custo estimado de Provider; esta issue define o ledger de créditos do produto sem duplicar telemetria.

## Objetivo

Criar carteira, transações append-only e preços configuráveis, com débito atômico e saldo auditável por Workspace.

## Modelo esperado

- `credit_wallets`: `workspace_id` único, `balance`, `monthly_allowance`, `purchased_credits`, `total_spent`, `cycle_started_at`, `created_at`, `updated_at`.
- `credit_transactions`: `id`, `workspace_id`, `user_id` nullable, `action_key`, `credits`, `quantity`, `balance_after`, `metadata`, `created_at`.
- `credit_prices`: `action_key` único, `category`, `credits`, `description`, `active`, `metadata`.
- Definir unidade/tipo, sinal de `credits`, ciclo mensal, allowance/purchased/spent, reembolso, idempotência e política de saldo negativo.
- Indexar wallet por Workspace, transactions por Workspace/data/action/user e prices por action/active.

## Critérios de aceite

- [ ] Migration Alembic reversível e modelos SQLAlchemy implementados.
- [ ] Há no máximo uma wallet ativa por Workspace e o saldo é transacional.
- [ ] Débito, crédito, estorno e idempotência estão documentados.
- [ ] Transactions são auditáveis e não podem ser alteradas silenciosamente.
- [ ] Prices suportam texto, imagem, melhorias e agentes sem hardcode disperso.
- [ ] Integração com #23 correlaciona consumo técnico e débito sem duplicar eventos.
- [ ] Testes cobrem concorrência, saldo insuficiente, ciclo, estorno e isolamento.
- [ ] Endpoint novo atualiza `docs/openapi.yaml` antes da implementação.

## Dependências

- Depends on: `workspaces`, `workspace_memberships`, `users`, consumo de Provider/Geração da #23.
- Related: ADR-001, ADR-005, ADR-007, ADR-008; issue #23.
