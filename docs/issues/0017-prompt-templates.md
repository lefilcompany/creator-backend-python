# Issue 0017: prompt templates

- ADR primaria: [`0001-llm-provider`](../adr/0001-llm-provider.md)
- ADRs relacionadas: [`0006-versioned-api-envelope`](../adr/0006-versioned-api-envelope.md), [`0007-openapi-first`](../adr/0007-openapi-first.md)
- Labels: `ai`, `prompts`, `observability`

## Papel

Centralizar templates e composicao de prompts de texto e imagem atras de uma boundary de aplicacao, evitando montagem direta em endpoints e providers.

## Criterios de aceite

- Conteudo, direcao de arte, imagem publicitaria, melhoria de copy e adaptacao de tom usam templates versionados.
- Renderizacao separa instrucoes de sistema, contexto e entrada do usuario.
- Entradas opcionais vazias sao normalizadas de forma deterministica.
- Entradas maliciosas nao reproduzem delimitadores estruturais do prompt.
- Identificador, versao e hash da entrada ficam disponiveis para Generation e Image metadata.
- Testes golden cobrem as combinacoes principais sem chamadas reais a providers.
