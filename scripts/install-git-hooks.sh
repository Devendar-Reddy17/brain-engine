#!/bin/sh
# Install optional Local Code Brain git hooks into the current repo's .git/hooks.
# Usage (from your repo root): sh path/to/install-git-hooks.sh
set -e

HOOK_SRC_DIR="$(cd "$(dirname "$0")/git-hooks" && pwd)"
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || true)"

if [ -z "$GIT_DIR" ]; then
  echo "Not inside a git repository." >&2
  exit 1
fi

mkdir -p "$GIT_DIR/hooks"
for hook in post-checkout post-merge post-rewrite post-commit; do
  cp "$HOOK_SRC_DIR/$hook" "$GIT_DIR/hooks/$hook"
  chmod +x "$GIT_DIR/hooks/$hook"
  echo "Installed $hook"
done

echo "Local Code Brain git hooks installed. They call 'brain git-refresh' on git operations."
