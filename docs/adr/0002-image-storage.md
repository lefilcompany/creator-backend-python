# ADR-002: Imagens fora do banco relacional

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 4
- Tracker: [#35](https://github.com/lefilcompany/creator-backend-python/issues/35)

## Decisão

Imagens ficam no Supabase Storage; PostgreSQL guarda somente referência, metadados e vínculo com a Generation. O domínio depende de `StorageProvider`.

## Consequências

Backups relacionais permanecem leves e o storage pode ser substituído. URLs, mime type, tamanho e ownership precisam ser validados no boundary.

## Issues vinculadas

#3, #5, #10, #16 e #33. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
