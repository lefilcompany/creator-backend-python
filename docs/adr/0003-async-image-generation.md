# ADR-003: Geração de imagens assíncrona

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 5
- Tracker: [#36](https://github.com/lefilcompany/creator-backend-python/issues/36)

## Decisão

POST cria um Generation Job e enfileira trabalho em Redis/RQ. O worker executa o provider, grava no storage e atualiza `PENDING`, `PROCESSING`, `COMPLETED` ou `FAILED`.

## Consequências

HTTP não fica bloqueado por latência de IA. Jobs precisam de idempotência, retries, observabilidade e tratamento de falha.

## Issues vinculadas

#3, #5, #7, #8, #12, #16, #25 e #33. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
