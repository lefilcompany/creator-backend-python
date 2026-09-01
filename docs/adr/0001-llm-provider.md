# ADR-001: Abstração de provider de LLM

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 3
- Tracker: [#34](https://github.com/lefilcompany/creator-backend-python/issues/34)

## Contexto

Creator precisa gerar texto sem acoplar o domínio a um fornecedor.

## Decisão

O domínio depende de provider interfaces; Gemini 2.5 Flash é o primeiro adapter de texto e Gemini Image é o primeiro adapter de imagem. A seleção ocorre em factories e credenciais ficam fora do código.

A composição de prompts é uma boundary de aplicação separada dos endpoints e dos providers. Templates são versionados e renderizados de forma determinística antes de chamar o provider; o identificador, versão e hash da entrada acompanham a Generation para observabilidade.

## Consequências

Trocar o vendor não exige alterar endpoints ou casos de uso. O adapter não configurado falha explicitamente, evitando geração falsa em produção.

## Issues vinculadas

#3, #9, #11, #13, [#17](../issues/0017-prompt-templates.md), #19, #23 e #27. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
