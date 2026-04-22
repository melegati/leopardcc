#!/usr/bin/env bash
set -euo pipefail

REPOS_FILE="repos.txt"
TARGET_DIR="repos"

if [[ ! -f "$REPOS_FILE" ]]; then
  echo "Error: $REPOS_FILE not found." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

while read -r repo_ref commit_hash || [[ -n "${repo_ref:-}" ]]; do
  [[ -z "${repo_ref:-}" || "${repo_ref:0:1}" == "#" ]] && continue

  if [[ -z "${commit_hash:-}" ]]; then
    echo "Skipping invalid line (missing commit hash): $repo_ref" >&2
    continue
  fi

  repo_url="https://github.com/${repo_ref}.git"
  repo_name="$(basename "$repo_ref")"
  repo_path="$TARGET_DIR/$repo_name"

  if [[ ! -d "$repo_path/.git" ]]; then
    git clone --no-checkout "$repo_url" "$repo_path"
  fi

  git -C "$repo_path" fetch --depth 1 origin "$commit_hash"
  git -C "$repo_path" checkout --detach FETCH_HEAD

done < "$REPOS_FILE"
