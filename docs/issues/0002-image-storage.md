# Tracker ADR-002: image storage adapter

- ADR: [`0002-image-storage`](../adr/0002-image-storage.md)
- Labels: `architecture`, `storage`

## Papel

Centralizar o progresso de #3, #5, #10, #16 e #33 sem criar uma tarefa duplicada.

## Encerramento

- Todas as issues vinculadas foram concluídas ou justificadamente substituídas.
- A decisão continua refletindo os trade-offs de armazenamento.

## Estratégia implementada

- `StorageProvider` abstrai upload, delete e geração de URL.
- Supabase Storage é o provider inicial para produção; provider local em disco atende
  desenvolvimento e testes sem chamadas externas.
- Objetos são gravados em chaves imutáveis por usuário, Content e versão.
- Bucket privado + URL assinada com expiração configurável é a política inicial de acesso.
- MIME type, tamanho, path e checksum SHA-256 são validados antes do upload.
- O fluxo de persistência faz upload antes de concluir o Generation Job; se upload falhar, o job é
  marcado como `FAILED`; se a conclusão relacional falhar após upload, o objeto recém-criado é
  removido.
- Soft delete retém objetos; purge físico usa `StorageProvider.delete` por `storage_path`.
