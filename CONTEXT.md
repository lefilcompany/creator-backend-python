# Creator

Creator is a multi-tenant platform for planning, generating, reviewing, and managing marketing content with AI assistance.

## Language

**Creator**:
The application as a whole. It contains several business capabilities and is not the name of an individual workflow or generated artifact.
_Avoid_: Create Bloom, Creator Bloom

**Workspace**:
The tenant boundary that owns business data, memberships, permissions, usage, and generated artifacts.
_Avoid_: Account, organization, team

**Global Role**:
A person's platform-wide authority, independent of any individual Workspace. The canonical values are `admin`, `gestor`, and `membro`.
_Avoid_: System permission, workspace role

**Workspace Role**:
A membership's authority inside one Workspace. The canonical values are `owner`, `admin`, `editor`, and `viewer`.
_Avoid_: Global role, user type

**Principal**:
The authenticated identity derived from a valid Creator access token. A Principal proves who is making a request but does not by itself prove access to a Workspace.
_Avoid_: User record, membership, session

**Auth Session**:
A revocable login relationship represented by one rotating refresh-token family. It may issue multiple short-lived access tokens over its lifetime.
_Avoid_: Access token, JWT, user

**Content**:
A persisted marketing artifact produced or managed by Creator, such as copy, an image, or a video. It is the output of a workflow, not the workflow itself.
_Avoid_: Creator, generation, job

**Generation**:
A request to an AI provider to produce or transform Content for a Workspace.
_Avoid_: Content, job, task

**Generation Job**:
The durable asynchronous execution of a Generation, including its lifecycle, attempts, result, and failure information.
_Avoid_: Generation, request, queue message

**Membership**:
The relationship that grants a Principal a Workspace Role inside one Workspace.
_Avoid_: global role, permission token

**Provider**:
An external capability adapter selected behind a stable Creator boundary, such as an AI model or object storage service.
_Avoid_: vendor, implementation detail

**Soft Delete**:
The business state in which a Content or related artifact remains recoverable in persistence but is excluded from normal reads by its `deleted_at` timestamp.
_Avoid_: hard delete, archive (unless the business behavior differs)

## Boundaries

- A Workspace owns Content, Generations, Generation Jobs, and Images.
- A Principal reaches Workspace data only through a Membership and its Workspace Role.
- A Generation describes intent; a Generation Job performs that intent asynchronously.
- A Content artifact is not an AI provider response: provider output must pass through the application boundary before becoming persisted Content.
