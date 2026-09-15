from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    content: str
    score: float
    metadata: Mapping[str, object] = field(default_factory=dict)


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed validated Workspace-owned documents."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a validated semantic search query."""


class SemanticRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        workspace_id: str,
        top_k: int | None = None,
    ) -> list[RetrievedDocument]:
        """Search only documents authorized for the provided Workspace."""


class ToolCallingProvider(Protocol):
    def invoke_with_tools(
        self,
        prompt: str,
        *,
        tools: Sequence[object],
        metadata: Mapping[str, object] | None = None,
    ) -> object:
        """Invoke a model with explicitly allowed tools."""
