# ADR-002: Imagens fora do banco relacional

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 4
- Tracker: [#35](https://github.com/lefilcompany/creator-backend-python/issues/35)

## Decisão

Imagens ficam no Supabase Storage; PostgreSQL guarda somente referência, metadados e vínculo com a Generation. O domínio depende de `StorageProvider`.

A implementação inicial usa buckets privados do Supabase Storage e expõe URLs assinadas com
expiração configurável. A URL persistida em `images.public_url` é uma URL utilizável no momento da
conclusão do job; endpoints de leitura devem regenerar URLs a partir de `images.storage_path`
quando a URL assinada expirar.

As chaves de objeto são imutáveis e seguem o formato
`users/{external_id}/contents/{content_id}/versions/{version}/image.{ext}`. O backend só deve
emitir URL para objetos depois de resolver o `User` atual e validar autorização de Workspace.

Soft delete mantém o objeto no storage para permitir retenção/restauração. Exclusão física é uma
operação de purge separada e idempotente: apagar o objeto pelo `storage_path` e manter o histórico
relacional necessário para auditoria conforme a política de retenção do produto.

## Consequências

Backups relacionais permanecem leves e o storage pode ser substituído. URLs, mime type, tamanho e ownership precisam ser validados no boundary.

## Issues vinculadas

#3, #5, #10, #16 e #33. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
