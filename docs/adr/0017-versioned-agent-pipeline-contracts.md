# ADR-017: versioned agent pipeline hand-off contracts

- Status: accepted
- Tracker: [docs/issues/0039](../issues/0039-versioned-agent-pipeline-contracts.md)

## Decision

Business, Planner, Writer, Artist and Reviewer exchange typed JSON envelopes. Each
edge declares its predecessor, successor, schema/version, required fields and the
only permitted transformation. Envelopes carry Workspace/Brand provenance,
correlation and context hashes; prompts are projections and never the workflow
state. Invalid or cross-Workspace envelopes are rejected at the application
boundary. Step audit data stores hashes and lineage, never hidden reasoning.

## Consequences

Retries and resume can use completed validated steps without reconstructing state
from free text. Reviewer refinements remain structured and attributable. Adding an
edge or changing a schema requires a new contract version and migration as needed.
