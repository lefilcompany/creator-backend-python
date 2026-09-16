# Issue 0030: generation cache

- ADR primária: [`0001-llm-provider`](../adr/0001-llm-provider.md)
- ADR tracker: [#34](https://github.com/lefilcompany/creator-backend-python/issues/34)
- GitHub: [#53](https://github.com/lefilcompany/creator-backend-python/issues/53)
- Labels: `backend`, `database`, `architecture`, `adr-001`

## Contexto

Gerações repetidas de texto e imagem aumentam custo e latência. Provider, Generation e Generation Job já possuem boundaries, mas não há camada persistente para reutilizar resultados válidos.

## Objetivo

Criar cache por Workspace com chave determinística, invalidação explícita e proteção contra reutilização entre tenants ou contextos incompatíveis.

## Modelo esperado

- `generation_cache`: `id`, `workspace_id`, `cache_key`, `generation_type`, `input_hash`, `result`, `hit_count`, `last_used_at`, `created_at`, `updated_at`.
- Definir JSONB ou referência de storage por tipo de output e garantir ownership/lifecycle de resultados não confiáveis.
- A chave deve incluir versão de prompt, Provider/modelo, parâmetros relevantes e schema; não omitir contexto de Brand.
- Definir unicidade, expiração/invalidação, contadores não negativos e índices de lookup/limpeza.
- Cache hit não deve criar indevidamente novo Content, Generation ou Generation Job.

## Critérios de aceite

- [ ] Migration Alembic reversível e modelo SQLAlchemy implementados.
- [ ] Lookup, concorrência, `hit_count` e `last_used_at` são transacionais.
- [ ] Isolamento e invalidação por Provider/modelo/prompt/schema são testados.
- [ ] Texto e imagem têm política de serialização e lifecycle documentada.
- [ ] Provider SDKs permanecem atrás de interfaces.
- [ ] Mudança de API atualiza `docs/openapi.yaml` antes da implementação.

## Dependências

- Depends on: `workspaces`, `generations`, `generation_jobs`, ADR-001.
- Related: ADR-003, ADR-005, ADR-007, ADR-008; issues #3, #19 e #33.
