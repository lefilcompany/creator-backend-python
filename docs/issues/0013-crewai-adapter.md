# Implement CrewAI adapter behind the multi-agent boundary

- ADR: [`0011-crewai-multi-agent-orchestration`](../adr/0011-crewai-multi-agent-orchestration.md)
- Labels: `agents`, `provider`, `implementation`

## Goal

Implementar o adapter CrewAI por trás de `MultiAgentOrchestrator`, preservando isolamento de Workspace e mantendo entradas, saídas e ferramentas dos agentes atrás de validações explícitas.

## Acceptance criteria

- O adapter concreto é o único ponto do código da aplicação que importa CrewAI.
- Nenhum workflow multiagentes confia em Workspace informado pelo cliente sem autorização.
- Entradas e saídas dos agentes são validadas antes de interagir com Content, Generation ou Generation Job.
- Há testes cobrindo configuração ausente, execução bem-sucedida controlada e falhas estruturadas.
