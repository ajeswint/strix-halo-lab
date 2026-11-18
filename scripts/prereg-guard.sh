#!/usr/bin/env bash
# scripts/prereg-guard.sh
#
# Guard: verifies that a pre-registered bar file:
#   1. exists and is inside the git repository
#   2. is tracked by git
#   3. has no uncommitted changes (index or worktree)
#   4. has its commit reachable from a pushed remote ref (via git fetch and merge-base --is-ancestor)
# Prints the prereg commit SHA and remote ref on success; exits non-zero otherwise.
#
# Usage:
#   scripts/prereg-guard.sh [options] <prereg-path> [remote-ref]
#
# Options:
#   --head       Check HEAD commit instead of the latest commit touching the file
#   --no-fetch   Skip running 'git fetch' (e.g. for offline use or local testing)
#   -h, --help   Show this help message

check_prereg() {
  local use_head=0
  local no_fetch=0
  local prereg_path=""
  local target_remote_ref=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --head)
        use_head=1
        shift
        ;;
      --no-fetch)
        no_fetch=1
        shift
        ;;
      -h|--help)
        echo "Usage: $0 [options] <prereg-path> [remote-ref]"
        echo ""
        echo "Options:"
        echo "  --head       Check HEAD commit instead of latest commit touching the file"
        echo "  --no-fetch   Skip 'git fetch'"
        echo "  -h, --help   Show this help message"
        return 0
        ;;
      -*)
        echo "ERROR: unknown option '$1'" >&2
        return 1
        ;;
      *)
        if [[ -z "$prereg_path" ]]; then
          prereg_path="$1"
        elif [[ -z "$target_remote_ref" ]]; then
          target_remote_ref="$1"
        else
          echo "ERROR: unexpected extra argument '$1'" >&2
          return 1
        fi
        shift
        ;;
    esac
  done

  if [[ -z "$prereg_path" ]]; then
    echo "ERROR: missing prereg path" >&2
    echo "Usage: $0 [options] <prereg-path> [remote-ref]" >&2
    return 1
  fi

  local repo_root
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: not inside a git repository" >&2
    return 1
  }

  if [[ ! -e "$prereg_path" ]]; then
    echo "ERROR: prereg file does not exist: $prereg_path" >&2
    return 1
  fi

  if [[ ! -f "$prereg_path" ]]; then
    echo "ERROR: prereg path is not a regular file: $prereg_path" >&2
    return 1
  fi

  local rel_path
  rel_path="$(realpath --relative-to="$repo_root" "$prereg_path" 2>/dev/null)" || {
    echo "ERROR: failed to resolve path for $prereg_path" >&2
    return 1
  }

  if [[ "$rel_path" == /* || "$rel_path" == ../* ]]; then
    echo "ERROR: prereg file is outside the git repository ($repo_root): $prereg_path" >&2
    return 1
  fi

  # 1. Verify tracked by git
  if ! git -C "$repo_root" ls-files --error-unmatch -- "$rel_path" >/dev/null 2>&1; then
    echo "ERROR: prereg file is not tracked by git: $rel_path" >&2
    return 1
  fi

  # 2. Verify HEAD exists and file has no uncommitted changes
  if ! git -C "$repo_root" rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "ERROR: repository has no HEAD commit" >&2
    return 1
  fi

  if ! git -C "$repo_root" diff HEAD --quiet -- "$rel_path" 2>/dev/null; then
    echo "ERROR: prereg file has uncommitted changes: $rel_path" >&2
    git -C "$repo_root" status --short -- "$rel_path" >&2
    return 1
  fi

  # 3. Determine commit SHA containing the prereg
  local prereg_commit
  if [[ $use_head -eq 1 ]]; then
    prereg_commit="$(git -C "$repo_root" rev-parse HEAD)"
  else
    prereg_commit="$(git -C "$repo_root" log -n 1 --format=%H -- "$rel_path")"
  fi

  if [[ -z "$prereg_commit" ]]; then
    echo "ERROR: could not determine commit for $rel_path" >&2
    return 1
  fi

  # 4. Determine remote and remote ref candidates
  local remote=""
  if [[ -n "$target_remote_ref" ]]; then
    if [[ "$target_remote_ref" == */* ]]; then
      remote="${target_remote_ref%%/*}"
    else
      remote="origin"
      target_remote_ref="origin/$target_remote_ref"
    fi
  else
    # Default remote is origin, or first available remote
    if git -C "$repo_root" remote | grep -qx "origin"; then
      remote="origin"
    else
      remote="$(git -C "$repo_root" remote | head -n 1)"
    fi
  fi

  if [[ -z "$remote" ]]; then
    echo "ERROR: no git remotes configured in repository" >&2
    return 1
  fi

  # 5. Fetch from remote if requested
  if [[ $no_fetch -eq 0 ]]; then
    if ! git -C "$repo_root" fetch "$remote" >/dev/null 2>&1; then
      echo "ERROR: git fetch failed for remote '$remote'" >&2
      return 1
    fi
  fi

  # 6. Verify commit reachability from pushed remote ref
  local matched_ref=""
  local checked_refs=()

  if [[ -n "$target_remote_ref" ]]; then
    checked_refs+=("$target_remote_ref")
    local resolved_ref="$target_remote_ref"
    if ! git -C "$repo_root" rev-parse --verify "$resolved_ref" >/dev/null 2>&1; then
      if git -C "$repo_root" rev-parse --verify "refs/remotes/$resolved_ref" >/dev/null 2>&1; then
        resolved_ref="refs/remotes/$resolved_ref"
      else
        echo "ERROR: remote ref '$target_remote_ref' not found on remote '$remote'" >&2
        return 1
      fi
    fi

    if git -C "$repo_root" merge-base --is-ancestor "$prereg_commit" "$resolved_ref" 2>/dev/null; then
      matched_ref="$target_remote_ref"
    else
      echo "ERROR: prereg commit $prereg_commit is not reachable from remote ref $target_remote_ref" >&2
      return 1
    fi
  else
    # Build candidate list:
    #   1. Current upstream tracking branch (if on remote)
    #   2. remote/<current-branch>
    #   3. remote/main
    #   4. remote/master
    #   5. Any other remote branch containing the commit
    local upstream
    upstream="$(git -C "$repo_root" rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
    if [[ -n "$upstream" && "$upstream" == "$remote/"* ]]; then
      checked_refs+=("$upstream")
    fi

    local curr_branch
    curr_branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ -n "$curr_branch" && "$curr_branch" != "HEAD" ]]; then
      local candidate="$remote/$curr_branch"
      if [[ " ${checked_refs[*]} " != *" $candidate "* ]]; then
        checked_refs+=("$candidate")
      fi
    fi

    if [[ " ${checked_refs[*]} " != *" $remote/main "* ]]; then
      checked_refs+=("$remote/main")
    fi
    if [[ " ${checked_refs[*]} " != *" $remote/master "* ]]; then
      checked_refs+=("$remote/master")
    fi

    # Check candidates
    local ref
    for ref in "${checked_refs[@]}"; do
      if git -C "$repo_root" rev-parse --verify "$ref" >/dev/null 2>&1; then
        if git -C "$repo_root" merge-base --is-ancestor "$prereg_commit" "$ref" 2>/dev/null; then
          matched_ref="$ref"
          break
        fi
      fi
    done

    # If still not found, check if ANY branch on this remote contains the commit
    if [[ -z "$matched_ref" ]]; then
      local any_branch
      while IFS= read -r any_branch; do
        [[ -z "$any_branch" ]] && continue
        if [[ " ${checked_refs[*]} " != *" $any_branch "* ]]; then
          checked_refs+=("$any_branch")
          if git -C "$repo_root" merge-base --is-ancestor "$prereg_commit" "$any_branch" 2>/dev/null; then
            matched_ref="$any_branch"
            break
          fi
        fi
      done < <(git -C "$repo_root" branch -r --contains "$prereg_commit" 2>/dev/null | sed -e 's/^[ *]*//' -e 's/ -> .*//' | grep "^$remote/" || true)
    fi

    if [[ -z "$matched_ref" ]]; then
      echo "ERROR: prereg commit $prereg_commit is not reachable from pushed remote branch" >&2
      echo "Checked remote refs: ${checked_refs[*]}" >&2
      echo "Ensure the commit containing $rel_path is pushed to $remote before launching." >&2
      return 1
    fi
  fi

  # Success: output prereg commit SHA and remote ref
  echo "prereg guard OK: commit $prereg_commit is reachable from $matched_ref"
  echo "  commit:     $prereg_commit"
  echo "  remote_ref: $matched_ref"
  echo "  file:       $rel_path"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  check_prereg "$@"
  exit $?
fi
