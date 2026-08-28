# ADR-004: Autenticação via Supabase Auth

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 6
- Tracker: [#37](https://github.com/lefilcompany/creator-backend-python/issues/37)

## Decisão

Supabase Auth emite JWTs; FastAPI valida assinatura, expiração e claims e cria um Principal. Autorização de Workspace permanece responsabilidade do backend.

## Issues vinculadas

#3, #14, #15, #20 e #25. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
