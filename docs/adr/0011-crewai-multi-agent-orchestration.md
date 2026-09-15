# ADR-011: CrewAI multi-agent orchestration boundary

- Status: accepted
- Fonte: decisão de instalação para arquitetura multiagentes
- Tracker: [docs/issues/0012-crewai-multi-agent-orchestration.md](../issues/0012-crewai-multi-agent-orchestration.md)

## Contexto

Creator precisa experimentar uma arquitetura multiagentes sem acoplar casos de uso, domínio ou endpoints HTTP diretamente ao CrewAI. A documentação do CrewAI descreve Crews para colaboração autônoma entre agentes e Flows para controle event-driven de automações, com suporte de instalação em Python `>=3.10,<3.14`.

## Decisão

Adicionar `crewai` como dependência do backend e restringir o runtime do projeto para Python `>=3.12,<3.14`. O uso do CrewAI deve ficar atrás de `MultiAgentOrchestrator`, em `creator.services.agents`, e a aplicação deve obter o orquestrador por factory. O adapter concreto de CrewAI será implementado em issue separada antes de qualquer endpoint ou Generation Job depender dele.

## Consequências

O projeto fica preparado para crews e flows sem espalhar imports de CrewAI pela aplicação. Ambientes Python 3.14 passam a falhar cedo na resolução do projeto, em vez de instalar uma dependência incompatível. A primeira implementação deve preservar isolamento de Workspace, tratar entradas e saídas de agentes como dados não confiáveis e manter provider integrations atrás de interfaces.

## Issues vinculadas

Tracker local: `docs/issues/0012-crewai-multi-agent-orchestration.md`.
Implementação local: `docs/issues/0013-crewai-adapter.md`.
Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
