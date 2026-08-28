#!/usr/bin/env bash
set -euo pipefail

repo="${GITHUB_REPOSITORY:-lefilcompany/creator-backend-python}"
base_url="https://github.com/${repo}"

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub authentication is required. Run: gh auth login -h github.com" >&2
  exit 1
fi

declare -A adr_file=(
  [001]="0001-llm-provider.md"
  [002]="0002-image-storage.md"
  [003]="0003-async-image-generation.md"
  [004]="0004-supabase-auth.md"
  [005]="0005-postgresql-sqlalchemy-alembic.md"
  [006]="0006-versioned-api-envelope.md"
  [007]="0007-openapi-first.md"
  [008]="0008-api-limits-and-soft-delete.md"
  [009]="0009-cloud-run-deployment.md"
  [010]="0010-architecture-governance.md"
)

declare -A tracker=(
  [001]=34 [002]=35 [003]=36 [004]=37 [005]=38
  [006]=39 [007]=40 [008]=41 [009]=42 [010]=43
)

declare -A tracker_title=(
  [001]="Tracker ADR-001: LLM provider boundary"
  [002]="Tracker ADR-002: image storage adapter"
  [003]="Tracker ADR-003: asynchronous image generation"
  [004]="Tracker ADR-004: Supabase Auth validation"
  [005]="Tracker ADR-005: persistence foundation"
  [006]="Tracker ADR-006: versioned API envelope"
  [007]="Tracker ADR-007: OpenAPI contract gate"
  [008]="Tracker ADR-008: API limits and soft delete"
  [009]="Tracker ADR-009: Cloud Run deployment"
  [010]="Tracker ADR-010: architecture governance"
)

declare -A implementation=(
  [001]="3 9 11 17 19 23 27"
  [002]="3 5 10 16 33"
  [003]="3 5 7 8 12 16 25 33"
  [004]="3 14 15 20 25"
  [005]="2 3 5 6 29"
  [006]="4 13 16 17 18 19 25 28"
  [007]="4 13 16 17 18 19 25 30 31"
  [008]="5 13 15 18 22 25"
  [009]="3 7 24 30 31 32"
  [010]="1 21 26 30 31 44"
)

declare -A primary=(
  [2]=005 [3]=005 [4]=006 [5]=005 [6]=005 [7]=009 [8]=003 [9]=001 [10]=002
  [11]=001 [12]=003 [13]=006 [14]=004 [15]=004 [16]=003 [17]=001 [18]=006
  [19]=001 [20]=004 [21]=010 [22]=008 [23]=001 [24]=009 [25]=006 [26]=010
  [27]=001 [28]=006 [29]=005 [30]=009 [31]=009 [32]=009 [33]=003 [44]=010
)

declare -A related=(
  [2]="" [3]="001 002 003 004 009" [4]="007" [5]="002 003 008" [6]=""
  [7]="003" [8]="001" [9]="" [10]="003" [11]="003" [12]="002" [13]="007 008"
  [14]="" [15]="008" [16]="002 006 007" [17]="006 007" [18]="007 008"
  [19]="006 007" [20]="" [21]="" [22]="" [23]="003" [24]="003"
  [25]="003 004 007 008" [26]="" [27]="003" [28]="003" [29]="003 008"
  [30]="007 010" [31]="006 007 010" [32]="010" [33]="002 005" [44]="001 002 003 004 005 006 007 008 009"
)

adr_link() {
  local adr="$1"
  printf '[ADR-%s](%s/blob/main/docs/adr/%s)' "$adr" "$base_url" "${adr_file[$adr]}"
}

create_label() {
  local name="$1"
  local color="$2"
  gh label create "$name" --repo "$repo" --color "$color" --force >/dev/null
}

for adr in "${!adr_file[@]}"; do
  create_label "adr-${adr}" "5319e7"
done
create_label tracker "1d76db"
create_label migration "fbca04"

update_issue() {
  local number="$1"
  local body="$2"
  shift 2
  gh issue edit "$number" --repo "$repo" --body "$body" "$@" >/dev/null
}

for number in "${!primary[@]}"; do
  adr="${primary[$number]}"
  current="$(gh issue view "$number" --repo "$repo" --json body --jq .body)"
  current="$(printf '%s\n' "$current" | sed '/^## Architecture traceability$/,$d')"
  section=$'\n\n## Architecture traceability\n\n'
  section+="- Primary decision: $(adr_link "$adr")"
  section+=$'\n'
  section+="- ADR tracker: #${tracker[$adr]}"
  if [[ -n "${related[$number]}" ]]; then
    section+=$'\n- Related decisions: '
    for related_adr in ${related[$number]}; do
      section+="$(adr_link "$related_adr"), "
    done
    section="${section%, }"
  fi
  section+=$'\n- Local index: `docs/ADR-ISSUE-TRACKER.md`'
  labels=(--add-label "adr-${adr}")
  if [[ "$number" == "44" ]]; then
    labels+=(--add-label migration)
  fi
  update_issue "$number" "${current}${section}" "${labels[@]}"
done

for adr in "${!tracker[@]}"; do
  number="${tracker[$adr]}"
  body="# Tracker $(adr_link "$adr")"
  body+=$'\n\nEsta issue acompanha a decisão arquitetural; ela não duplica uma tarefa de implementação. Feche-a somente quando todas as issues vinculadas estiverem concluídas, substituídas ou explicitamente dispensadas.'
  body+=$'\n\n## Issues de implementação\n'
  for child in ${implementation[$adr]}; do
    if [[ "$child" == "1" ]]; then
      body+="- [x] #${child}"$'\n'
    else
      body+="- [ ] #${child}"$'\n'
    fi
  done
  body+=$'\n## Regra de manutenção\n\n- A implementação referencia sua ADR primária e este tracker.\n- Uma nova tarefa que preserva esta decisão é adicionada aqui.\n- Uma mudança de decisão exige nova ADR, que deve superseder esta ADR quando aplicável.\n- Índice local: `docs/ADR-ISSUE-TRACKER.md`.\n'
  update_issue "$number" "$body" --title "${tracker_title[$adr]}" --add-label tracker --add-label "adr-${adr}"
done

current="$(gh issue view 1 --repo "$repo" --json body --jq .body)"
current="$(printf '%s\n' "$current" | sed '/^## Materialização atual$/,$d')"
materialized=$'\n\n## Materialização atual\n\nA decisão aprovada foi desdobrada em ADR-001 a ADR-009. O acompanhamento fica em #34 a #42 e o índice versionado é `docs/ADR-ISSUE-TRACKER.md`. A governança está em #43.'
update_issue 1 "${current}${materialized}" --add-label adr-010

echo "GitHub ADR tracker reconciled for ${repo}."
