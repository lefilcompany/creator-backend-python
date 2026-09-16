# ADR-014: Specialist-agent image generation workflow

- Status: accepted
- Fonte: `Fluxo de geração de imagem - creator.pdf` e plano de implementação aprovado
- Tracker: [`docs/issues/0032-agent-image-generation-workflow.md`](../issues/0032-agent-image-generation-workflow.md), [#56](https://github.com/lefilcompany/creator-backend-python/issues/56)

## Contexto

O fluxo direto de imagem gera um prompt e chama um Provider, mas não separa análise de marca, planejamento, escrita, geração e revisão. Isso reduz a qualidade do prompt, dificulta auditoria e não oferece um ciclo explícito de refação ou aprovação humana.

## Decisão

Adicionar um workflow próprio e assíncrono para imagem com os papéis `Business`, `Planner`, `Writer`, `Artist` e `Reviewer`. A máquina de estados pertence ao Creator e persiste cada etapa, prompt, output estruturado, decisão e erro sanitizado. CrewAI permanece atrás de `MultiAgentOrchestrator` como adapter substituível; não controla transições de negócio nem acesso a Workspace.

O workflow recebe `brand_id`, campanha, persona, quantidade, orientações extras, modo de revisão humana e extensões controladas. O Workspace é derivado da Brand autorizada. Cada execução cria um novo Content e preserva imagens candidatas como versões imutáveis. O fluxo suporta aprovação automática ou pausa para aprovação humana e limita refações a uma configuração padrão de três tentativas.

O Revisor usa uma interface multimodal provider-neutral. RAG é opcional e sempre recebe o `workspace_id` autorizado; Brand e BrandSettings continuam sendo o contexto mínimo. Vídeo fica fora da primeira implementação, mas os contratos não devem assumir que o único media kind futuro será imagem.

## Consequências

O sistema passa a ter maior latência e custo por execução, compensados por prompts especializados, validação de schemas, revisão objetiva, idempotência, limites e rastreabilidade. Os endpoints existentes de geração direta permanecem compatíveis durante a migração. Nenhum SDK de Provider ou CrewAI pode ser importado por domínio, aplicação ou endpoint.

## Issues vinculadas

- Tracker: `docs/issues/0032-agent-image-generation-workflow.md`.
- Contratos, estados e persistência: `docs/issues/0033-agent-workflow-persistence.md`.
- Agentes, prompts e RAG: `docs/issues/0034-specialist-agent-contracts.md`.
- Providers e revisão multimodal: `docs/issues/0035-multimodal-image-reviewer.md`.
- API, worker e migração do fluxo assíncrono: `docs/issues/0036-agent-workflow-api-worker.md`.

Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
