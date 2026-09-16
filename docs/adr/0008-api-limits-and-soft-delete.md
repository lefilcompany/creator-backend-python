# ADR-008: Limites de API, provedores e soft delete

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 10
- Tracker: [#41](https://github.com/lefilcompany/creator-backend-python/issues/41)

## Decisão

Listagens usam `page`, `limit` e `sort`; texto aceita até 20.000 caracteres; uploads até 10 MB em PNG/JPG/WEBP; exclusão usa `deleted_at`.

O consumo da API é controlado por um rate limiter de janela deslizante de 1 segundo,
com limite padrão de 5 requisições por endpoint, classe e identidade. Rotas autenticadas
usam o `Principal.subject`; login e signup usam o endereço do cliente como fallback
necessário antes da autenticação. Endpoints baratos e endpoints de Generation usam
namespaces separados.

Redis é o backend distribuído obrigatório em produção. O script Lua executa limpeza,
contagem e admissão atomicamente, permitindo que múltiplas instâncias compartilhem
contadores. O backend em memória existe somente para testes. Se Redis estiver indisponível,
rotas de Generation falham fechado com `503 RATE_LIMITER_UNAVAILABLE`, enquanto endpoints
baratos seguem fail-open e registram métrica.

Limites excedidos retornam `429 RATE_LIMIT_EXCEEDED` no envelope padrão, com `Retry-After`
e headers auxiliares de limite/reset. Métricas Prometheus usam somente classe, endpoint
canônico e resultado como labels; não incluem Principal, Workspace, IP ou request ID.

## Issues vinculadas

#5, #13, #15, #18, #19, #22, #25 e [rate limiting](../issues/0024-api-rate-limiting.md).
Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
