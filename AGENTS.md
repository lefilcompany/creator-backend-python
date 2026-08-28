# Creator agent guidelines

## Mission

Build Creator as a multi-tenant, contract-first Python backend. Preserve the domain language in `CONTEXT.md`; do not introduce synonyms for Workspace, Principal, Content, Generation, or Generation Job.

## Non-negotiable engineering rules

- Every material architectural decision must have an ADR in `docs/adr/`.
- Every ADR must have one tracker issue and one or more linked implementation issues in `docs/issues/` and, when authenticated, in `lefilcompany/creator-backend-python`. Use `docs/ADR-ISSUE-TRACKER.md` as the canonical index.
- Define or update `docs/openapi.yaml` before changing API behavior.
- Keep provider integrations behind interfaces; application code must not import vendor SDKs directly.
- Enforce Workspace isolation at the application boundary and never trust a client-supplied workspace identifier without authorization.
- Treat generated output and uploads as untrusted data. Validate type, size, ownership, and lifecycle.
- Use UTC timestamps, soft delete where the ADR requires it, and structured errors with `request_id`.
- New behavior requires tests. Run `make check` before handoff.

## Subagents

Subagents are configured globally under `/home/emanueljtrodrigues/.agents/skills/*/agents/openai.yaml`. Use them for bounded research or review, never as a substitute for the primary agent reading the repository context and ADRs. A subagent must return evidence (files, commands, and decisions), and its output must be reviewed before it changes the repository.

Recommended delegation:

- `grilling` / `domain-modeling`: expose unresolved domain decisions and update vocabulary.
- `code-review` / `code-review-and-quality`: review a completed increment against standards and the ADR.
- `diagnosing-bugs`: investigate failures before proposing fixes.
- `research` / `source-driven-development`: verify external technical facts against primary documentation.

## Delivery workflow

1. Read `CONTEXT.md`, relevant ADRs, and the issue linked to the task.
2. Make the smallest testable increment.
3. Run focused tests, then `make check`.
4. Update ADR/issue traceability when the decision changes.
5. Report changed files, checks, and unresolved external blockers.
