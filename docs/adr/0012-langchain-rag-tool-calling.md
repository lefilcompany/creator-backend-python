# ADR-012: LangChain RAG and tool-calling boundary

- Status: accepted
- Fonte: decisão de instalação para embeddings, RAG e tool calling
- Tracker: [docs/issues/0021-langchain-rag-tool-calling.md](../issues/0021-langchain-rag-tool-calling.md)

## Contexto

Creator precisa preparar busca semântica sobre Content e outros artefatos de Workspace, além de permitir tool calling controlado para fluxos de geração assistida. LangChain oferece interfaces estáveis para modelos de chat, embeddings, vector stores e ferramentas, mas a aplicação não deve depender diretamente do framework em endpoints, casos de uso ou domínio.

## Decisão

Adicionar `langchain`, `langchain-google-genai` e `langchain-chroma` como dependências diretas do backend. O uso deve ficar atrás das interfaces `EmbeddingProvider`, `SemanticRetriever` e `ToolCallingProvider`, em `creator.services.retrieval`. Gemini continua sendo o Provider inicial para embeddings e chat/tool calling, usando `langchain-google-genai`; Chroma é o vector store local inicial para desenvolvimento e testes.

## Consequências

Creator pode evoluir para RAG e busca semântica sem espalhar imports de LangChain pelo código de aplicação. Todo índice e toda consulta devem ser escopados por Workspace; entradas de Content, documentos recuperados, metadados e resultados de tools continuam sendo dados não confiáveis. A primeira implementação concreta deve validar ownership, limite de `top_k`, metadados permitidos, tool allowlist e fallback quando o Provider estiver ausente.

## Issues vinculadas

Tracker local: `docs/issues/0021-langchain-rag-tool-calling.md`.
Implementação local: `docs/issues/0022-langchain-retrieval-adapters.md`.
Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
