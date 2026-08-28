# ADR-006: API versionada com envelope estável

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 8
- Tracker: [#39](https://github.com/lefilcompany/creator-backend-python/issues/39)

## Decisão

Rotas públicas usam `/api/v1`. Sucesso retorna `success`, `data` e `meta.request_id`; falhas retornam `success`, `error.code`, `error.message` e `meta.request_id`.

## Issues vinculadas

#4, #13, #16, #17, #18, #19, #25 e #28. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
