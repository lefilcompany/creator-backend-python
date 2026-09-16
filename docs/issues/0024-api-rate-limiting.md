# Issue 0024: distributed API and provider rate limiting

- ADR primária: [`0008-api-limits-and-soft-delete`](../adr/0008-api-limits-and-soft-delete.md)
- ADR tracker: [`#41`](https://github.com/lefilcompany/creator-backend-python/issues/41)
- Labels: `security`, `api`, `redis`, `observability`

## Objetivo

Controlar o consumo da API e dos provedores de IA por identidade autenticada, endpoint
e janela de tempo, compartilhando contadores entre instâncias de produção.

## Entrega

- Redis obrigatório em produção e backend em memória somente para testes.
- Janela deslizante atômica de 1 segundo e limite padrão de 5 requisições.
- Namespaces distintos para rate limiting e RQ.
- Respostas estruturadas `429` com `Retry-After`.
- Política fail-closed para Generation e fail-open para endpoints baratos.
- Métricas Prometheus sem alta cardinalidade.

## Critérios de aceite

- Requests autenticados não dependem somente do IP.
- Instâncias compartilham os contadores Redis.
- Concorrência, reset, aliases e indisponibilidade têm cobertura de testes.
- O contrato OpenAPI documenta respostas, headers e `/metrics`.
