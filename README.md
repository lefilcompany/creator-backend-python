# Creator backend

Fundação Python 3.12/FastAPI para o Creator, reconstruída a partir do ADR de 27/08/2026. A migração do sistema anterior está deliberadamente separada como backlog porque o repositório de origem não estava acessível durante a bootstrap.

## Quick start

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health/live
```

Localmente, instale as dependências com `make install` e execute `make check`.

## Arquitetura

- `src/creator/api`: transporte HTTP, contratos e respostas versionadas.
- `src/creator/domain`: vocabulário e modelos de negócio independentes de vendors.
- `src/creator/infrastructure`: banco, fila, autenticação e configurações.
- `src/creator/services`: providers de IA e storage atrás de interfaces.
- `docs/adr`: decisões arquiteturais; `docs/issues`: issues rastreáveis.

O contrato inicial está em [`docs/openapi.yaml`](docs/openapi.yaml). Os adapters reais Supabase/Gemini serão implementados nas issues correspondentes; a fundação fornece boundaries testáveis e um provider explícito que falha com segurança quando não configurado.

## GitHub issues

O script `scripts/create_github_issues.sh` publica de forma idempotente os arquivos de `docs/issues/` usando `gh`, adicionando labels e preservando os links ADR. Ele exige `gh auth status` válido e nunca imprime tokens.
