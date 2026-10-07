# Issue 0026: brand knowledge entities

- ADR primária: [`0012-langchain-rag-tool-calling`](../adr/0012-langchain-rag-tool-calling.md)
- ADR tracker: [`docs/issues/0021`](0021-langchain-rag-tool-calling.md)
- GitHub: [#49](https://github.com/lefilcompany/creator-backend-python/issues/49)
- Labels: `backend`, `database`, `architecture`, `priority-high`, `adr-012`

## Contexto

Creator possui `brands`, `brand_settings` e o boundary de RAG/embeddings, mas não possui persistência para fontes e fragmentos indexáveis. O legado Create Bloom não deve ser replicado.

## Objetivo

Criar Brand Knowledge por Brand e Workspace para ingestão, chunking, embeddings e recuperação semântica futura.

## Modelo esperado

- `brand_knowledge_documents`: `id`, `workspace_id`, `brand_id`, `title`, `source`, `metadata`, `created_at`, `updated_at`; avaliar `deleted_at`.
- `brand_knowledge_chunks`: `id`, `workspace_id`, `brand_id`, `document_id`, `content`, `embedding`, `chunk_index`, `metadata`, `created_at`.
- Usar UUID, timestamps UTC e FK composta ou restrição equivalente para impedir mistura de tenants.
- Manter o modelo independente de SDK de Provider e definir índices para `(document_id, chunk_index)` e filtros por `(workspace_id, brand_id)`.

## Critérios de aceite

- [x] Migration Alembic reversível e modelos SQLAlchemy implementados (`0017_brand_knowledge`).
- [x] Ownership de Workspace/Brand, tipo de embedding e metadata documentados: FK composta impede mistura de Brand/Workspace; embeddings são arrays JSONB provider-neutral, metadata é objeto JSONB e chunks aceitam de 1 a 100.000 caracteres.
- [x] Unicidade e índices cobrem ingestão, reprocessamento e recuperação (`document_id + chunk_index` e filtros por Workspace/Brand).
- [x] Testes de modelo cobrem constraints, isolamento estrutural, Soft Delete/cascatas e ordenação de chunks.
- [ ] Se houver API, `docs/openapi.yaml` é atualizado antes da implementação.

## Implementação

Não há API nesta entrega. A persistência fica disponível para a futura ingestão e recuperação sem importar SDK de Provider. Documentos usam Soft Delete; chunks são removidos em cascata com o documento e preservam a ordenação por `chunk_index`.

## Dependências

- Depends on: `workspaces`, `workspace_memberships`, `brands`.
- Related: ADR-005, ADR-007, ADR-008, ADR-012; issues #20, #21 e #22.
