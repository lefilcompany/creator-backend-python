# Issue 0013: Gemini image generator

- ADR primária: [`0001-llm-provider`](../adr/0001-llm-provider.md)
- ADRs relacionadas: [`0003-async-image-generation`](../adr/0003-async-image-generation.md)
- Labels: `ai`, `provider`, `jobs`

## Papel

Implementar a integração de geração de imagens com Gemini usando o SDK oficial Google GenAI, mantendo o provider atrás de boundary substituível para o worker RQ.

## Critérios de aceite

- `GEMINI_API_KEY` e `GEMINI_IMAGE_MODEL` configuram autenticação e modelo.
- Timeout, quota, conteúdo bloqueado e resposta inválida viram exceções classificadas.
- Retry ocorre somente em falhas transitórias e respeita limite configurado.
- Resultado normalizado inclui bytes, mime type, dimensões, modelo, prompt e metadados não sensíveis.
- Testes usam fake/mock e não chamam a rede.
