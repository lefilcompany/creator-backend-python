# Issue 0023: text Content improvement preview

- ADR primaria: [`0013-content-improvement-preview`](../adr/0013-content-improvement-preview.md)
- ADRs relacionadas: [`0001-llm-provider`](../adr/0001-llm-provider.md), [`0006-versioned-api-envelope`](../adr/0006-versioned-api-envelope.md), [`0007-openapi-first`](../adr/0007-openapi-first.md), [`0008-api-limits-and-soft-delete`](../adr/0008-api-limits-and-soft-delete.md)
- Labels: `api`, `ai`, `content`, `prompts`

## Papel

Melhorar textos de Content ou texto avulso com objetivos controlados, retornando a previa atualizada e a justificativa separadamente, sem alterar o original.

## Criterios de aceite

- `POST /api/v1/content/improve` aceita `shorten`, `persuasive`, `formal`, `seo` e `audience_adaptation`.
- Objetivo invalido retorna 422 no envelope versionado.
- A resposta separa `text` e `justification`.
- O Content original nao e alterado; a entrega retorna `persistence: preview_only`.
- Prompts sao especificos por objetivo e versionados.
- Entrada de texto respeita 20.000 caracteres e o alvo e exatamente um de `text` ou `content_id`.
- Falhas do LLM nao persistem alteracoes e retornam erro padronizado.
