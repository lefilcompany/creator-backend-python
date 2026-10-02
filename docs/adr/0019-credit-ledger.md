# ADR-019: Ledger de créditos por Workspace

- Status: accepted
- Tracker: [#38](https://github.com/lefilcompany/creator-backend-python/issues/38)
- Issue: [0031-credits](../issues/0031-credits.md)

## Decisão

Créditos são unidades inteiras e não monetárias. `credit_wallets` é tenant-scoped e possui uma única linha por Workspace. `credit_transactions` é um ledger append-only: débitos usam `credits < 0`, créditos e reembolsos usam `credits > 0`; `balance_after` registra o saldo após a operação. O saldo nunca pode ficar negativo. A aplicação bloqueia a wallet (`FOR UPDATE`) antes de validar e inserir o movimento, no mesmo commit.

`monthly_allowance` é a concessão do ciclo atual; `purchased_credits` é o saldo comprado restante. `total_spent` só cresce com débitos (reembolsos não apagam nem reescrevem o histórico). O ciclo mensal é reiniciado por uma operação explícita, que cria uma transação de concessão e atualiza `cycle_started_at`; não há cron implícito nesta migration.

Cada operação que pode ser repetida deve fornecer `idempotency_key`, única por Workspace. Repetições retornam o movimento original; a mesma chave com payload diferente é erro. A correlação com consumo técnico da issue #23 fica em `credit_transactions.metadata` (por exemplo, `generation_id`, `provider_usage_id` e `correlation_id`), sem duplicar evento de telemetria.

`credit_prices` é configuração global, separada das wallets tenant-scoped. A categoria e `action_key` permitem adicionar texto, imagem, melhorias e agentes sem hardcode nos casos de uso; preços inativos não podem ser usados para novos débitos.

## Consequências

- A unicidade da wallet e da idempotência é garantida pelo banco.
- Transações não têm `updated_at` nem delete lógico; correções são novos movimentos de crédito/estorno.
- O enforcement de ownership ocorre no repositório/caso de uso através da Membership; o `workspace_id` do cliente nunca é autoridade suficiente.
