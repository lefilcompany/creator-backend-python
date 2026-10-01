# ADR-018: event-driven agent pipeline with transactional outbox

- Status: accepted
- Tracker: [docs/issues/0040](../issues/0040-event-driven-agent-pipeline.md)

## Decision

The HTTP boundary remains synchronous only for accepting a workflow. Agent stages
are processed asynchronously. PostgreSQL is the source of truth for workflow
steps and a transactional `outbox_events` table. Redis/RQ is the initial transport;
the event contract must not depend on that transport and can later be published
to Kafka without changing agent inputs or outputs.

Each stage persists its validated output and the next event in one transaction.
Consumers are idempotent and use the event's run, step, Workspace and hashes to
reject duplicates, stale predecessors, and cross-Workspace data.
