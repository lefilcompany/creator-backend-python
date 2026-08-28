#!/usr/bin/env bash
set -euo pipefail

repo="${GITHUB_REPOSITORY:-lefilcompany/creator-backend-python}"

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub authentication is required. Run: gh auth login -h github.com" >&2
  exit 1
fi

gh repo view "$repo" >/dev/null
for label in architecture security migration; do
  gh label create "$label" --repo "$repo" --color 5319e7 --force >/dev/null
done

for file in docs/issues/*.md; do
  title="$(sed -n 's/^# //p' "$file" | head -1)"
  if gh issue list --repo "$repo" --state all --search "in:title $title" --json title --jq '.[].title' | grep -Fqx "$title"; then
    echo "exists: $title"
  else
    gh issue create --repo "$repo" --title "$title" --body-file "$file"
  fi
done
