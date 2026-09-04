# ADR-011: Core Resource CRUD

- Status: accepted
- Fonte: implementacao do core relacional do Creator
- Tracker: local

## Contexto

Creator precisa expor CRUD transacional para os recursos centrais do dominio alem de User e Workspace: Brand, Project, Content, Generation, Asset e Brand Settings.

## Decisao

O backend Python e a fonte canonica do modelo de dominio. As tabelas novas usam PostgreSQL via SQLAlchemy/Alembic, UUIDs, timestamps UTC, `deleted_at` para Soft Delete e `workspace_id` como limite de tenant.

Rotas REST versionadas retornam o envelope padrao e dependem da Membership do Principal para ler ou escrever dados do Workspace. Upload binario de Asset permanece fora do CRUD inicial; o recurso persiste metadados e referencias de storage.

## Consequencias

O frontend pode migrar para a API do backend sem depender diretamente das migrations Supabase legadas. Relacionamentos opcionais de Brand e Project passam a existir em Content, Generation e Asset sem quebrar os fluxos de geracao ja existentes.

## Issues vinculadas

Issue local: [0020-core-resource-crud](../issues/0020-core-resource-crud.md). Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
