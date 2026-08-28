# ADR-008: Limites de payload e soft delete

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 10
- Tracker: [#41](https://github.com/lefilcompany/creator-backend-python/issues/41)

## Decisão

Listagens usam `page`, `limit` e `sort`; texto aceita até 20.000 caracteres; uploads até 10 MB em PNG/JPG/WEBP; exclusão usa `deleted_at`.

## Issues vinculadas

#5, #13, #15, #18, #22 e #25. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
