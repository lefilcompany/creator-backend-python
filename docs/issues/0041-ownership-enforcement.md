# Ownership enforcement for protected resources

- Status: in progress
- ADR primária: [ADR-011 Core Resource CRUD](../adr/0011-core-resource-crud.md)
- ADR relacionada: [ADR-004 Supabase Auth](../adr/0004-supabase-auth.md)

## Objetivo

Garantir que Content, Image Generation e Settings sejam sempre resolvidos pelo
Principal autenticado e pelo escopo autorizado do Workspace, sem permitir
enumeração por identificador.

## Implementação

- Leituras e listagens usam métodos `*_for_user`.
- Alteração e exclusão de Content recebem `user_id` obrigatório no repositório.
- Criação de Generation Job de imagem valida Membership com papel mínimo `editor`.
- Recursos ausentes ou fora do escopo retornam a mesma semântica de não encontrado.

## Checklist

- [x] Content update/delete escopados pelo Principal
- [x] Generation não pode referenciar Content de outro Workspace
- [x] Image Generation create escopado pelo Principal
- [x] Settings acessados apenas pelo usuário autenticado
- [x] Teste estrutural impede rotas de negócio sem Principal e contrato OpenAPI sem bearer security
- [x] Auditoria completa das demais entidades e endpoints
- [ ] Testes de autorização por endpoint
