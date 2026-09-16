# Issue 0035: multimodal image reviewer provider

- ADR: [`0014-agent-image-generation-workflow`](../adr/0014-agent-image-generation-workflow.md)
- Labels: `agents`, `provider`, `implementation`
- GitHub: [#59](https://github.com/lefilcompany/creator-backend-python/issues/59)

## Scope

Adicionar a interface provider-neutral de revisão multimodal e seu adapter Gemini, validando decisão, score, feedback e violações de segurança.

## Acceptance criteria

- [x] SDK Gemini permanece somente no adapter.
- [x] Imagem, prompt, briefing e contexto de marca chegam ao Revisor como dados validados.
- [x] Violações de segurança são terminais; falhas de qualidade permitem refação limitada.
- [x] Provider fake cobre aprovação, refação, rejeição e resposta inválida.
