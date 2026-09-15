from collections.abc import Mapping, Sequence

from creator.config import Settings
from creator.services.retrieval.provider import (
    EmbeddingProvider,
    RetrievedDocument,
    SemanticRetriever,
    ToolCallingProvider,
)


class RetrievalProviderNotConfiguredError(RuntimeError):
    """Raised when retrieval or tool-calling providers cannot safely be used."""


class UnconfiguredEmbeddingProvider:
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise RetrievalProviderNotConfiguredError("Embedding provider is not configured")

    def embed_query(self, text: str) -> list[float]:
        raise RetrievalProviderNotConfiguredError("Embedding provider is not configured")


class UnconfiguredSemanticRetriever:
    def search(
        self,
        query: str,
        *,
        workspace_id: str,
        top_k: int | None = None,
    ) -> list[RetrievedDocument]:
        raise RetrievalProviderNotConfiguredError("Semantic retriever is not configured")


class UnconfiguredToolCallingProvider:
    def invoke_with_tools(
        self,
        prompt: str,
        *,
        tools: Sequence[object],
        metadata: Mapping[str, object] | None = None,
    ) -> object:
        raise RetrievalProviderNotConfiguredError("Tool-calling provider is not configured")


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.langchain_enabled:
        # LangChain adapters belong to ADR-012's implementation issue.
        return UnconfiguredEmbeddingProvider()
    return UnconfiguredEmbeddingProvider()


def create_semantic_retriever(settings: Settings) -> SemanticRetriever:
    if settings.langchain_enabled:
        # Retrieval must enforce Workspace isolation before exposing any vector store.
        return UnconfiguredSemanticRetriever()
    return UnconfiguredSemanticRetriever()


def create_tool_calling_provider(settings: Settings) -> ToolCallingProvider:
    if settings.langchain_enabled:
        # Tool calling must use an allowlist and validate tool inputs/outputs first.
        return UnconfiguredToolCallingProvider()
    return UnconfiguredToolCallingProvider()
