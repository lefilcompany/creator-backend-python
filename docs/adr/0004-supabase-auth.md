# ADR-004: Autenticação via Supabase Auth

- Status: accepted
- Fonte: `adr_creator_python.pdf`, seção 6
- Tracker: [#37](https://github.com/lefilcompany/creator-backend-python/issues/37)

## Decisão

Supabase Auth emite JWTs; FastAPI valida assinatura, expiração e claims e cria um Principal. Autorização de Workspace permanece responsabilidade do backend.

O `sub` do JWT Supabase é a identidade externa canônica e é persistido em `users.external_id`.
Quando um token válido chega à API de negócio, o backend resolve o `User` local por
`external_id`; se ele não existir, cria um `User` com Global Role `membro`; se existir,
sincroniza atributos não autoritativos vindos do token, como email e nome de exibição.

As APIs de negócio aceitam apenas access tokens de usuários autenticados. Claims obrigatórias:
`iss`, `aud`, `exp`, `iat`, `sub`, `role` e `session_id`; `role` deve ser `authenticated`.
Tokens ausentes, expirados, com issuer/audience incorretos, assinatura inválida ou algoritmo
não permitido retornam a mesma resposta externa `401 AUTHENTICATION_INVALID`.

Revogação de sessão segue a semântica de access token localmente verificável: um access token já
emitido pode ser aceito até `exp`. Revogação imediata depende de expiração curta configurada no
Supabase Auth ou de uma checagem online futura contra o Auth server. Para chaves assimétricas, a
API usa JWKS com cache de no máximo 10 minutos e deve buscar novas chaves quando o `kid` muda;
durante migração, tokens HS256 legados usam `SUPABASE_JWT_SECRET`, enquanto tokens assimétricos
continuam passando por JWKS.

## Issues vinculadas

#3, #14, #15, #20 e #25. Consulte o [tracker central](../ADR-ISSUE-TRACKER.md).
