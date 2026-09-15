# Tracker ADR-011: CrewAI multi-agent orchestration boundary

- ADR: [`0011-crewai-multi-agent-orchestration`](../adr/0011-crewai-multi-agent-orchestration.md)
- Labels: `architecture`, `agents`, `provider`

## Papel

Centralizar o progresso da instalação do CrewAI e da boundary de orquestração multiagentes sem duplicar as tarefas executáveis.

## Encerramento

- `crewai` está declarado como dependência do projeto.
- O runtime Python do projeto exclui versões incompatíveis com CrewAI.
- A aplicação expõe uma interface estável para orquestração multiagentes.
- A implementação concreta do adapter CrewAI foi entregue por issue vinculada.
