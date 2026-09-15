# ADR-013: Text Content improvement preview

- Status: accepted
- Fonte: entrega `POST /api/v1/content/improve`, 2026-09-15
- Tracker: [docs/issues/0023](../issues/0023-content-improvement-preview.md)

## Contexto

Creator precisa melhorar texto existente ou texto avulso com objetivos controlados, retornando a versao sugerida e a justificativa da alteracao. A decisao de persistir a sugestao como novo Content ou versao afeta historico, autoria, auditoria e Workspace isolation.

## Decisao

`POST /api/v1/content/improve` produz uma previa sincronica e nao altera o Content original. A resposta explicita `persistence: preview_only`; criar novo Content ou nova versao exige uma regra de negocio futura e explicita.

O endpoint aceita exatamente um alvo: `text` ou `content_id`. Quando `content_id` e usado, o Content deve estar visivel ao Principal e pertencer ao `workspace_id` autorizado. O provider LLM recebe um prompt versionado por objetivo e deve responder JSON com `text` e `justification`.

Os objetivos aceitos sao `shorten`, `persuasive`, `formal`, `seo` e `audience_adaptation`. Objetivos fora desse conjunto retornam 422 pelo contrato.

## Consequencias

A melhoria fica segura para revisao humana e nao cria historico persistido sem intencao explicita. O contrato preserva o limite de 20.000 caracteres de texto da ADR-008 e mantem provider integrations atras da interface LLM da ADR-001.

## Issues vinculadas

[docs/issues/0023](../issues/0023-content-improvement-preview.md). Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
