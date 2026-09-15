# Tracker ADR-012: LangChain RAG and tool-calling boundary

- ADR: [`0012-langchain-rag-tool-calling`](../adr/0012-langchain-rag-tool-calling.md)
- Labels: `architecture`, `rag`, `embeddings`, `provider`

## Papel

Centralizar a instalação do LangChain e a criação das boundaries para embeddings, busca semântica e tool calling.

## Encerramento

- Dependências LangChain estão declaradas no projeto.
- Configurações de embeddings, vector store e RAG estão versionadas.
- A aplicação expõe interfaces estáveis sem acoplar endpoints ou domínio ao LangChain.
- A implementação concreta dos adapters LangChain foi entregue por issue vinculada.
