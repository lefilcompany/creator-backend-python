# Creator backend

Fundação Python 3.12/FastAPI para o Creator, reconstruída a partir do ADR de 27/08/2026. A migração do sistema anterior está deliberadamente separada como backlog porque o repositório de origem não estava acessível durante a bootstrap.

## Quick start

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

Localmente, instale as dependências pinadas e inicie a aplicação:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn creator.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger fica disponível em `http://localhost:8000/docs`; ReDoc em `http://localhost:8000/redoc`.
Execute a validação local com `ruff check src tests`, `ruff format --check src tests`, `mypy src` e `pytest`. Em ambientes com `make`, `make check` roda o mesmo conjunto.

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
