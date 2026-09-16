# Creator backend

Fundação Python 3.12/FastAPI para o Creator, reconstruída a partir do ADR de 27/08/2026. A migração do sistema anterior está deliberadamente separada como backlog porque o repositório de origem não estava acessível durante a bootstrap.

## Quick start

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

O Compose executa `alembic upgrade head` no serviço `migrate` antes de iniciar a API e o worker.
Se estiver usando o Postgres do próprio Compose, mantenha `DATABASE_URL` com host `db`, como em
`.env.example`; use `localhost` apenas quando rodar a API diretamente na máquina host.

Localmente, instale as dependências pinadas e inicie a aplicação:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
alembic upgrade head
uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload
```

Em outro processo, execute o worker de Generation Job de imagem:

```bash
creator-worker image-generation
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
alembic upgrade head
uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload
```

Em outro PowerShell, execute o worker de Generation Job de imagem:

```powershell
creator-worker image-generation
```

Swagger fica disponível em `http://localhost:8000/docs`; ReDoc em `http://localhost:8000/redoc`.
Métricas agregadas do rate limiter ficam disponíveis em `http://localhost:8000/metrics`.
Execute a validação local com `ruff check src tests`, `ruff format --check src tests`, `mypy src` e `pytest`. Em ambientes com `make`, `make check` roda o mesmo conjunto.

Para gerar Content de texto ou imagem com Gemini real, configure `GEMINI_API_KEY` no `.env`.
Sem essa chave, os endpoints protegidos continuam disponíveis, mas chamadas de geração retornam
erro estruturado de provider não configurado depois da autenticação e autorização de Workspace.

O signup Creator cria o primeiro Workspace e uma Membership `owner` para o Principal:

```json
{
  "email": "principal@example.com",
  "password": "correct-password",
  "workspace": {
    "name": "Creator Workspace"
  }
}
```

Use o `data.workspace.id` retornado como `workspace_id` em `POST /api/v1/content/generate`.
Também é possível criar outro Workspace em `POST /api/v1/workspaces` e soft-delete em
`DELETE /api/v1/workspaces/{id}`.

## Arquitetura

- `src/creator/main.py`: entrada executável FastAPI.
- `src/creator/api`: transporte HTTP, contratos e respostas versionadas.
- `src/creator/domain`: vocabulário e modelos de negócio independentes de vendors.
- `src/creator/infrastructure`: banco, fila, autenticação e configurações.
- `src/creator/services`: providers de IA e storage atrás de interfaces.
- `docs/adr`: decisões arquiteturais; `docs/issues`: issues rastreáveis.

O contrato inicial está em [`docs/openapi.yaml`](docs/openapi.yaml). Os adapters reais Supabase/Gemini serão implementados nas issues correspondentes; a fundação fornece boundaries testáveis e um provider explícito que falha com segurança quando não configurado.

## GitHub issues

O script `scripts/create_github_issues.sh` publica de forma idempotente os arquivos de `docs/issues/` usando `gh`, adicionando labels e preservando os links ADR. Ele exige `gh auth status` válido e nunca imprime tokens.
