# Status do projeto Creator

Atualizado em: 2026-09-15

Este documento resume o que ja foi feito no backend Creator e o que ainda deve ser feito, usando como referencia o vocabulario de `CONTEXT.md`, as decisoes em `docs/adr/` e o indice `docs/ADR-ISSUE-TRACKER.md`.

## Visao geral

Creator esta sendo construido como um backend Python/FastAPI contract-first, multi-tenant, com isolamento por Workspace, autenticacao baseada em Supabase Auth, persistencia relacional em PostgreSQL via SQLAlchemy/Alembic e integracoes externas sempre atras de interfaces de Provider.

O projeto ja tem uma fundacao executavel: API versionada em `/api/v1`, envelope padrao de resposta, modelo relacional, migrations, repositorios, Unit of Work, geracao de Content de texto, Generation Job assincrono para imagem, storage de imagem, CRUD dos recursos centrais, prompts versionados e testes cobrindo os principais boundaries.

As frentes ainda pendentes se concentram em adapters concretos para capacidades mais novas, migracao do legado, operacionalizacao de deploy/CI/GitHub e evolucoes de produto ainda nao decididas por ADR.

## O que ja foi feito

### Fundacao de dominio e arquitetura

- `CONTEXT.md` define o vocabulario canonico do dominio: Workspace, Principal, Content, Generation, Generation Job, Membership, Provider e Soft Delete.
- A arquitetura separa HTTP (`src/creator/api` e `src/creator/main.py`), dominio (`src/creator/domain`), aplicacao (`src/creator/application`), infraestrutura (`src/creator/infrastructure`), repositorios (`src/creator/repositories`) e providers (`src/creator/services`).
- `AGENTS.md` estabelece o fluxo de entrega: ler contexto/ADRs/issues, manter OpenAPI antes de mudar comportamento, criar ADR para decisoes materiais, usar interfaces para providers, preservar isolamento de Workspace e rodar checks antes do handoff.
- `docs/ADR-ISSUE-TRACKER.md` relaciona ADRs e issues locais/remotas.

ADRs relacionadas: ADR-010.

### Contrato HTTP e envelope versionado

- `docs/openapi.yaml` existe como contrato versionado e cobre endpoints publicos em `/api/v1`.
- A API usa envelope de sucesso com `success`, `data` e `meta.request_id`.
- A API usa envelope de erro com `success`, `error.code`, `error.message` e `meta.request_id`.
- Existem handlers centralizados para `HTTPException` e erros de validacao.
- Existem health checks em `/health` e `/health/live`.

ADRs relacionadas: ADR-006 e ADR-007.

### Autenticacao e autorizacao de Workspace

- Supabase Auth esta atras de boundary propria em `src/creator/infrastructure/auth.py`.
- Login e signup por email/senha estao expostos em `/api/v1/auth/login` e `/api/v1/auth/signup`.
- JWTs Supabase sao validados considerando issuer, audience, expiracao, `iat`, `sub`, `role`, `session_id` e algoritmos permitidos.
- `sub` e mapeado para `users.external_id`.
- O backend resolve ou cria o `User` local a partir do Principal autenticado.
- Signup cria o primeiro Workspace e uma Membership `owner`.
- APIs protegidas resolvem o usuario atual por `/api/v1/users/me`.
- Operacoes de Workspace e recursos centrais passam por Membership e Workspace Role.

ADRs relacionadas: ADR-004, ADR-006, ADR-008 e ADR-011 Core Resource CRUD.

### Persistencia relacional

- PostgreSQL e o banco relacional definido.
- SQLAlchemy fica restrito a infraestrutura.
- Alembic controla as migrations reproduziveis.
- Casos de uso dependem de repositorios e Unit of Work, nao de `Session` SQLAlchemy diretamente.
- Existem migrations ate `0008_content_query_indexes`.
- O modelo relacional inclui Users, Settings, Workspaces, Workspace Memberships, Brands, Brand Settings, Projects, Contents, Generations, Generation Jobs, Generation Job Status Events, Images e Assets.
- Recursos sujeitos a remocao de negocio usam `deleted_at` para Soft Delete.
- Indices de consulta foram adicionados para Content, incluindo ordenacao por Workspace e busca textual com `pg_trgm`.

ADRs relacionadas: ADR-005, ADR-008 e ADR-011 Core Resource CRUD.

### CRUD dos recursos centrais

Ja existem endpoints versionados e protegidos para:

- Users: CRUD administrativo e `/api/v1/users/me`.
- Settings do usuario: leitura e atualizacao em `/api/v1/settings`.
- Workspaces: listar, criar, ler, atualizar e soft-delete.
- Brands: listar, criar, ler, atualizar e soft-delete.
- Brand Settings: ler, upsert, atualizar e soft-delete por Brand.
- Projects: listar, criar, ler, atualizar e soft-delete.
- Contents: criar, ler, listar, atualizar e soft-delete.
- Generations: listar, criar, ler, atualizar e soft-delete.
- Assets: listar, criar, ler, atualizar e soft-delete.

Esses endpoints retornam o envelope padrao e aplicam escopo por Workspace/Membership.

ADRs relacionadas: ADR-005, ADR-006, ADR-007, ADR-008 e ADR-011 Core Resource CRUD.

### Geracao de Content de texto

- `POST /api/v1/content/generate` gera Content textual de forma sincronica.
- O fluxo valida Workspace visivel ao Principal autenticado.
- O prompt e montado pelo catalogo central em `src/creator/prompts`.
- Gemini 2.5 Flash e o primeiro adapter real de texto quando `GEMINI_API_KEY` esta configurada.
- Sem provider configurado, a aplicacao falha explicitamente com erro estruturado.
- O resultado e persistido como Content `TEXT` com Generation `TEXT` vinculada.
- Erros de provider, timeout, quota, conteudo bloqueado, resposta invalida e persistencia sao mapeados para respostas padronizadas.

ADRs relacionadas: ADR-001, ADR-005, ADR-006, ADR-007 e ADR-008.

### Preview de melhoria de Content

- `POST /api/v1/content/improve` implementa a previa sincronica de melhoria textual.
- O endpoint aceita exatamente um alvo: `text` ou `content_id`.
- Objetivos aceitos: `shorten`, `persuasive`, `formal`, `seo` e `audience_adaptation`.
- Para `content_id`, o Content precisa pertencer ao Workspace autorizado e estar visivel ao Principal.
- A resposta separa `text`, `justification`, `original_text`, `objective`, `persistence`, `content_id` e `prompt_template`.
- A semantica atual e `preview_only`: o Content original nao e alterado.
- Saida do provider precisa ser JSON com `text` e `justification`.

ADRs relacionadas: ADR-013, ADR-001, ADR-006, ADR-007 e ADR-008.

### Imagens, storage e Generation Jobs

- `POST /api/v1/images/generate` cria um Generation Job e enfileira geracao de imagem.
- `POST /api/v1/images/{id}/regenerate` cria um novo Generation Job de regeneracao a partir de uma imagem existente.
- `GET /api/v1/images/{id}` consulta status do Generation Job e regenera URL assinada quando a imagem foi concluida.
- Redis/RQ e a fila inicial para Generation Jobs de imagem.
- O worker `creator-worker image-generation` processa jobs, chama provider de imagem, persiste no storage e atualiza status.
- Status suportados: `PENDING`, `PROCESSING`, `COMPLETED` e `FAILED`.
- Ha controle de idempotencia via `Idempotency-Key`.
- Supabase Storage e provider de producao; storage local atende desenvolvimento/testes.
- Objetos de imagem seguem chaves imutaveis por usuario, Content e versao.
- MIME type, tamanho, dimensoes, checksum e path sao validados no boundary.
- Soft Delete retem objetos; purge fisico permanece uma operacao separada.

ADRs relacionadas: ADR-001, ADR-002, ADR-003, ADR-005, ADR-006, ADR-008 e ADR-009.

### Prompts e observabilidade de prompt

- Templates de prompt ficam centralizados em `src/creator/prompts`.
- Existem templates para geracao de Content, direcao de arte, imagem publicitaria, melhoria de copy e adaptacao de tom.
- Renderizacao separa instrucoes de sistema, contexto e entrada do usuario.
- Testes golden existem em `tests/golden/prompts`.
- Generation e metadados carregam informacoes como identificador/versao/hash do prompt conforme a decisao da ADR-001.

ADRs relacionadas: ADR-001.

### Preparacao para CrewAI

- `crewai` esta declarado como dependencia.
- O runtime do projeto foi restringido para Python `>=3.12,<3.14`.
- Existe a interface `MultiAgentOrchestrator`.
- Existe factory de orquestrador em `src/creator/services/agents/factory.py`.
- O adapter concreto ainda nao foi implementado; a factory retorna um orquestrador nao configurado que falha explicitamente.

ADRs relacionadas: ADR-011 CrewAI multi-agent orchestration boundary.

### Preparacao para LangChain, RAG e tool calling

- `langchain`, `langchain-google-genai` e `langchain-chroma` estao declarados como dependencias.
- Existem interfaces `EmbeddingProvider`, `SemanticRetriever` e `ToolCallingProvider`.
- Existem factories em `src/creator/services/retrieval/factory.py`.
- Configuracoes de embedding, vector store, collection e `rag_top_k` estao versionadas em `Settings`.
- Os adapters concretos ainda nao foram implementados; as factories retornam providers nao configurados que falham explicitamente.

ADRs relacionadas: ADR-012.

### Deploy e operacao local

- Existe `Dockerfile`.
- Existe `docker-compose.yml` com banco, Redis, migracao, API e worker.
- O README documenta quick start, execucao local, worker, Swagger/ReDoc e checks.
- `Makefile` centraliza validacao local via `make check`.

ADRs relacionadas: ADR-009.

### Testes existentes

Ha testes cobrindo:

- Estrutura da aplicacao.
- API e envelope.
- Fundacao de dominio.
- Modelos relacionais.
- Repositorios e Unit of Work.
- Integridade relacional.
- Fila.
- Storage.
- Providers Gemini de texto e imagem.
- Prompts e golden files.
- Geracao de Content.
- Worker de geracao de imagem.

## O que ainda sera feito

### Migracao do legado

- Obter snapshot ou acesso autenticado ao repositorio legado `lefilcompany/create-bloom-73`.
- Inventariar rotas, formatos de dados e comportamentos visiveis ao usuario.
- Produzir matriz de compatibilidade entre legado e backend atual.
- Migrar comportamentos com testes de contrato e vinculo a issues/ADRs.

ADR principal: ADR-010. Issue local: `docs/issues/0011-source-migration-inventory.md`.

### Adapter concreto CrewAI

- Implementar adapter CrewAI atras de `MultiAgentOrchestrator`.
- Garantir que CrewAI seja importado apenas no adapter concreto.
- Validar entradas e saidas dos agentes antes de tocar Content, Generation ou Generation Job.
- Preservar autorizacao de Workspace para qualquer workflow multiagente.
- Cobrir configuracao ausente, execucao controlada e falhas estruturadas com testes.

ADR principal: ADR-011 CrewAI. Issue local: `docs/issues/0013-crewai-adapter.md`.

### Adapters LangChain para RAG e tool calling

- Implementar embeddings Gemini atras de `EmbeddingProvider`.
- Implementar busca semantica via Chroma atras de `SemanticRetriever`.
- Implementar tool calling controlado atras de `ToolCallingProvider`.
- Garantir filtro obrigatorio por Workspace em indexacao e consulta.
- Respeitar `rag_top_k` e metadados permitidos.
- Implementar allowlist de tools e validacao de entradas/saidas antes de alterar recursos de dominio.
- Criar testes para configuracao ausente, embedding controlado, consulta por Workspace e rejeicao de tool nao permitida.

ADR principal: ADR-012. Issue local: `docs/issues/0022-langchain-retrieval-adapters.md`.

### Evolucao da melhoria de Content

- Decidir em ADR futura se uma melhoria aprovada vira novo Content, nova versao de Content ou outro recurso de revisao.
- Definir historico, autoria, auditoria e comportamento de rollback antes de persistir sugestoes.
- Manter a semantica atual `preview_only` ate a regra de negocio ser explicitamente decidida.

ADR principal: ADR-013.

### Operacao de storage e ciclo de vida

- Formalizar e implementar rotina operacional de purge fisico idempotente para objetos marcados por Soft Delete, quando a politica de retencao do produto estiver definida.
- Garantir regeneracao de URLs assinadas em todos os endpoints de leitura que exponham imagens ou assets privados.
- Evoluir upload binario de Asset, que hoje persiste metadados e referencias de storage, mas nao representa ainda um fluxo completo de upload de arquivo pelo CRUD inicial.

ADRs relacionadas: ADR-002, ADR-008 e ADR-011 Core Resource CRUD.

### Deploy, CI e ambiente

- Validar imagem Docker em CI.
- Configurar deploy protegido para Cloud Run com secrets de Supabase, Redis, Gemini e storage.
- Definir ambientes e politicas de promocao.
- Garantir que `make check` rode como gate de qualidade.

ADR principal: ADR-009.

### Governanca e rastreabilidade remota

- Manter `docs/ADR-ISSUE-TRACKER.md` atualizado sempre que ADRs/issues mudarem.
- Reconciliar issues locais com GitHub quando houver autenticacao disponivel.
- Usar `Refs #<issue>` ou `Closes #<issue>` nos PRs conforme criterio de aceite.
- Corrigir eventual ambiguidade de numeracao entre as duas ADRs `0011` criando uma convencao futura se isso passar a atrapalhar rastreabilidade.

ADR principal: ADR-010.

### Hardening de API e dominio

- Expandir testes de contrato contra `docs/openapi.yaml`.
- Revisar todos os endpoints que aceitam `workspace_id`, `brand_id`, `project_id` ou `content_id` para garantir validacao cruzada de ownership em cenarios compostos.
- Manter limites de payload, paginacao e ordenacao alinhados a ADR-008.
- Garantir que todo dado gerado por IA, upload ou tool externa continue sendo tratado como nao confiavel.

ADRs relacionadas: ADR-004, ADR-006, ADR-007 e ADR-008.

## Mapa resumido por ADR

| ADR | Decisao | Status no repositorio | Proximo passo |
| --- | --- | --- | --- |
| ADR-001 | Providers de LLM atras de interfaces | Gemini texto e imagem integrados; prompts versionados | Evoluir novos providers sem vazar SDK para aplicacao |
| ADR-002 | Imagens fora do banco relacional | Supabase/local storage, metadados e URL assinada | Definir/implementar purge e completar ciclos de leitura de assets |
| ADR-003 | Geracao de imagens assincrona | RQ, worker, status e idempotencia implementados | Fortalecer operacao, observabilidade e recuperacao em producao |
| ADR-004 | Supabase Auth | Login/signup/JWT/Principal/User local implementados | Ajustar revogacao imediata se o produto exigir checagem online |
| ADR-005 | PostgreSQL, SQLAlchemy e Alembic | Modelos, migrations, repositorios e Unit of Work implementados | Continuar novas persistencias via repositorios/UoW |
| ADR-006 | Envelope versionado | Envelope aplicado em sucesso e erro | Expandir testes de contrato |
| ADR-007 | OpenAPI first | Contrato existe e cobre endpoints atuais | Manter OpenAPI antes de qualquer mudanca de API |
| ADR-008 | Limites e Soft Delete | Paginacao, limites e `deleted_at` aplicados | Revisar edge cases e rotinas operacionais de retencao |
| ADR-009 | Deploy containerizado | Dockerfile/Compose prontos | CI, Cloud Run e secrets protegidos |
| ADR-010 | Governanca | ADRs, issues e tracker existem | Reconciliar GitHub e migracao do legado |
| ADR-011 Core CRUD | CRUD dos recursos centrais | Endpoints/modelos/repositorios implementados | Completar upload binario de Asset e maturar regras compostas |
| ADR-011 CrewAI | Boundary multiagente | Dependencia e interface existem | Implementar adapter concreto CrewAI |
| ADR-012 | LangChain/RAG/tool calling | Dependencias, config e interfaces existem | Implementar adapters concretos |
| ADR-013 | Preview de melhoria textual | Endpoint `preview_only` implementado | Decidir persistencia futura de sugestoes |

## Leituras principais

- `CONTEXT.md`: vocabulario e boundaries de negocio.
- `docs/ADR-ISSUE-TRACKER.md`: indice canonico ADR/issues.
- `docs/adr/`: decisoes arquiteturais aceitas.
- `docs/issues/`: backlog versionado e criterios de aceite.
- `docs/openapi.yaml`: contrato HTTP.
- `README.md`: execucao local, Docker, worker e checks.
