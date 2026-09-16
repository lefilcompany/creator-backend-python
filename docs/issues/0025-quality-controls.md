# Issue 0025: automated quality controls

- ADR primária: [`0010-architecture-governance`](../adr/0010-architecture-governance.md)
- ADR tracker: [`#43`](https://github.com/lefilcompany/creator-backend-python/issues/43)
- Labels: `process`, `quality`, `security`, `ci`

## Objetivo

Automatizar os controles de qualidade e segurança antes do merge, mantendo os comandos
locais e de CI alinhados.

## Entrega

- `make check` centraliza Ruff lint, format check, mypy e pytest.
- `make security` executa `pip-audit` e Gitleaks.
- CI bloqueia o merge quando qualquer scanner falha.
- `.gitleaks.toml` contém somente allowlists de placeholders determinísticos documentados.
- `.pre-commit-config.yaml` fornece hooks opcionais de Ruff e mypy.

## Política

Qualquer vulnerabilidade reportada pelo `pip-audit` é bloqueante, incluindo críticas.
Novas exceções de secrets exigem valor exato, justificativa no arquivo de configuração e
revisão no ADR-010 ou nesta issue.
