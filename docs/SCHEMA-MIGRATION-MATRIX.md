# Schema migration matrix

The PDF is the target schema. The existing generation workflow is still active,
so legacy tables remain registered until each consumer is migrated.

| Current model | PDF target | Migration work |
| --- | --- | --- |
| `Content` | `post_structure` | Replace content payload with post fields and planning ownership. |
| `Generation` | `design_structure` | Move provider intent to the design structure contract. |
| `Image` | `generated_image` | Persist signed URL, size, resolution, ratio and review status. |
| `GenerationJob` | worker state outside the PDF model | Move lifecycle to the worker/queue boundary; do not add a new table silently. |
| `Project` | `campaigns`/`planning` | Replace project ownership and filters with campaign/planning scope. |
| `Asset` | `brand_assets` | Separate brand-owned uploads from generated images. |
| `Settings` | `notification_preferences` or user profile fields | Remove after consumers are migrated. |
| `AgentWorkflowRun` / `AgentWorkflowStep` | `post_structure` workflow fields | Consolidate only after the workflow API is migrated. |

## Endpoints schema-native disponíveis

- `Campaign`: `/api/v1/campaigns`
- `Persona`: `/api/v1/personas`
- `Planning`: `/api/v1/planning`
- `PostStructure`: `/api/v1/post-structures`
- `BrandAsset`: `/api/v1/brand-assets`
- `GeneratedImage` (leitura): `/api/v1/generated-images/{id}`

The migration is intentionally staged: dropping a legacy table before its
repositories and workers are migrated would destroy active behavior.
