# ADR-009: Deploy containerizado

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 11
- Tracker: [#42](https://github.com/lefilcompany/creator-backend-python/issues/42)

## Decisão

O backend é empacotado em Docker e preparado para Cloud Run, com Supabase como dependência gerenciada e Redis externo. CI valida a imagem; deploy é protegido por ambiente/secrets.

## Issues vinculadas

#3, #7, #24, #30, #31 e #32. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
