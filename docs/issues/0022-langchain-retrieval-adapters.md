# Implement LangChain retrieval adapters

- ADR: [`0012-langchain-rag-tool-calling`](../adr/0012-langchain-rag-tool-calling.md)
- Labels: `rag`, `embeddings`, `provider`, `implementation`

## Goal

Implementar adapters LangChain para embeddings Gemini, busca semântica via Chroma e tool calling controlado, preservando isolamento de Workspace.

## Acceptance criteria

- Imports de LangChain ficam restritos aos adapters de infraestrutura.
- Documentos indexados carregam `workspace_id` e metadados mínimos permitidos.
- Consultas semânticas filtram obrigatoriamente por Workspace e respeitam `rag_top_k`.
- Tool calling usa allowlist explícita de tools e valida entradas e saídas antes de tocar Content, Generation ou Generation Job.
- Há testes cobrindo configuração ausente, embedding controlado, consulta filtrada por Workspace e rejeição de tool não permitida.
