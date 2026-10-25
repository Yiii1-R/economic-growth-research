#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_root"

git add -A

if git diff --cached --quiet; then
    printf '%s\n' 'No changes to commit.'
    exit 0
fi

commit_message=${1:-"Auto snapshot: $(date '+%Y-%m-%d %H:%M:%S')"}
git commit -m "$commit_message"
git push

printf '%s\n' "Pushed commit: $(git rev-parse --short HEAD)"
