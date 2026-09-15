# Tracker ADR-004: Supabase Auth validation

- ADR: [`0004-supabase-auth`](../adr/0004-supabase-auth.md)
- Labels: `security`, `auth`

## Papel

Centralizar o progresso de #3, #14, #15, #20 e #25 sem criar uma tarefa duplicada.

## Encerramento

- Todas as issues vinculadas foram concluídas ou justificadamente substituídas.
- A decisão continua refletindo o boundary Supabase Auth e a autorização de Workspace.

## Estratégia implementada

- JWTs Supabase são validados por assinatura, issuer, audience, expiração, `iat`, `sub`,
  `role`, `session_id` e algoritmo permitido.
- `sub` é mapeado para `users.external_id`; o backend cria o `User` local ausente e sincroniza
  email/nome de exibição de usuários existentes.
- Respostas 401 de token são padronizadas como `AUTHENTICATION_INVALID`, sem expor motivo
  sensível ao cliente.
- HS256 legado usa `SUPABASE_JWT_SECRET`; tokens assimétricos usam JWKS com cache limitado para
  suportar rotação de chaves.
