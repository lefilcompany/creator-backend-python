# ADR-001: Abstração de provider de LLM

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 3
- Tracker: [#34](https://github.com/lefilcompany/creator-backend-python/issues/34)

## Contexto

Creator precisa gerar texto sem acoplar o domínio a um fornecedor.

## Decisão

O domínio depende de `LLMProvider`; Gemini 2.5 Flash é o primeiro adapter. A seleção ocorre em uma factory e credenciais ficam fora do código.

## Consequências

Trocar o vendor não exige alterar endpoints ou casos de uso. O adapter não configurado falha explicitamente, evitando geração falsa em produção.

## Issues vinculadas

#3, #9, #11, #17, #19, #23 e #27. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
