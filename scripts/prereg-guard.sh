#!/usr/bin/env bash
# scripts/prereg-guard.sh
#
# Guard: verifies that a pre-registered bar file:
#   1. exists and is inside the git repository
#   2. is not empty
#   3. is tracked by git without skip-worktree or assume-unchanged flags
#   4. has no uncommitted changes (worktree hash matches HEAD blob)
#   5. has its commit reachable from a pushed remote ref (verified via git ls-remote)
# Prints the prereg commit SHA and remote ref on success; exits non-zero otherwise.
#
# Usage:
#   scripts/prereg-guard.sh [options] <prereg-path> [remote-ref]
#
# Options:
#   --head       Check HEAD commit instead of the latest commit touching the file
#   --no-fetch   Skip git fetch (still verifies against remote via ls-remote)
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
        echo "  --no-fetch   Skip 'git fetch' (still verifies against remote via ls-remote)"
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

  # Reject empty prereg file
  if [[ ! -s "$prereg_path" ]] || [[ -z "$(tr -d '[:space:]' < "$prereg_path")" ]]; then
    echo "ERROR: prereg file is empty: $prereg_path" >&2
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

  # Reject if file has skip-worktree or assume-unchanged flags
  local ls_flags
  ls_flags="$(git -C "$repo_root" ls-files -v -- "$rel_path" 2>/dev/null | awk '{print $1}')"
  if [[ "$ls_flags" =~ ^[hSs]$ ]]; then
    echo "ERROR: prereg file has skip-worktree or assume-unchanged flag ($ls_flags): $rel_path" >&2
    return 1
  fi

  # 2. Verify HEAD exists and file has no uncommitted changes
  if ! git -C "$repo_root" rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "ERROR: repository has no HEAD commit" >&2
    return 1
  fi

  local head_blob
  head_blob="$(git -C "$repo_root" rev-parse "HEAD:$rel_path" 2>/dev/null || true)"
  if [[ -z "$head_blob" ]]; then
    echo "ERROR: prereg file has uncommitted changes (not in HEAD commit): $rel_path" >&2
    return 1
  fi

  local file_hash
  file_hash="$(git -C "$repo_root" hash-object "$prereg_path" 2>/dev/null || true)"
  if [[ "$file_hash" != "$head_blob" ]]; then
    echo "ERROR: prereg file has uncommitted changes (worktree hash $file_hash != HEAD blob $head_blob): $rel_path" >&2
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
  local available_remotes
  available_remotes="$(git -C "$repo_root" remote)"
  if [[ -z "$available_remotes" ]]; then
    echo "ERROR: no git remotes configured in repository" >&2
    return 1
  fi

  local remote=""
  local target_branch=""

  if [[ -n "$target_remote_ref" ]]; then
    local r
    for r in $available_remotes; do
      if [[ "$target_remote_ref" == "$r"/* ]]; then
        remote="$r"
        target_branch="${target_remote_ref#$r/}"
        break
      elif [[ "$target_remote_ref" == "refs/remotes/$r"/* ]]; then
        remote="$r"
        target_branch="${target_remote_ref#refs/remotes/$r/}"
        break
      fi
    done

    if [[ -z "$remote" ]]; then
      if grep -qx "origin" <<< "$available_remotes"; then
        remote="origin"
      else
        remote="$(head -n 1 <<< "$available_remotes")"
      fi
      target_branch="$target_remote_ref"
      target_remote_ref="$remote/$target_branch"
    fi
  else
    if grep -qx "origin" <<< "$available_remotes"; then
      remote="origin"
    else
      remote="$(head -n 1 <<< "$available_remotes")"
    fi
  fi

  # 5. Verify commit reachability from pushed remote ref
  local matched_ref=""

  if [[ -n "$target_remote_ref" ]]; then
    local ls_out=""
    if [[ "$target_branch" == refs/* ]]; then
      ls_out="$(git -C "$repo_root" ls-remote "$remote" "$target_branch" 2>/dev/null || true)"
    else
      ls_out="$(git -C "$repo_root" ls-remote "$remote" "refs/heads/$target_branch" 2>/dev/null || true)"
      if [[ -z "$ls_out" ]]; then
        ls_out="$(git -C "$repo_root" ls-remote "$remote" "$target_branch" 2>/dev/null || true)"
      fi
    fi

    if [[ -z "$ls_out" ]]; then
      echo "ERROR: remote ref '$target_remote_ref' not found on remote '$remote'" >&2
      return 1
    fi

    local remote_sha
    remote_sha="$(awk '{print $1}' <<< "$ls_out" | head -n 1)"
    if [[ -z "$remote_sha" ]]; then
      echo "ERROR: failed to get SHA for remote ref '$target_remote_ref' on remote '$remote'" >&2
      return 1
    fi

    if ! git -C "$repo_root" rev-parse --verify "$remote_sha" >/dev/null 2>&1; then
      if [[ $no_fetch -eq 0 ]]; then
        git -C "$repo_root" fetch "$remote" "$remote_sha" >/dev/null 2>&1 || \
          git -C "$repo_root" fetch "$remote" "refs/heads/$target_branch" >/dev/null 2>&1 || true
      fi
    fi

    if ! git -C "$repo_root" rev-parse --verify "$remote_sha" >/dev/null 2>&1; then
      echo "ERROR: remote commit $remote_sha for ref '$target_remote_ref' not found in local repository" >&2
      return 1
    fi

    if git -C "$repo_root" merge-base --is-ancestor "$prereg_commit" "$remote_sha" 2>/dev/null; then
      matched_ref="$target_remote_ref"
    else
      echo "ERROR: prereg commit $prereg_commit is not reachable from remote ref $target_remote_ref" >&2
      return 1
    fi
  else
    local candidate_branches=()
    local upstream
    upstream="$(git -C "$repo_root" rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
    if [[ -n "$upstream" && "$upstream" == "$remote/"* ]]; then
      candidate_branches+=("${upstream#$remote/}")
    fi

    local curr_branch
    curr_branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ -n "$curr_branch" && "$curr_branch" != "HEAD" ]]; then
      if [[ " ${candidate_branches[*]} " != *" $curr_branch "* ]]; then
        candidate_branches+=("$curr_branch")
      fi
    fi

    if [[ " ${candidate_branches[*]} " != *" main "* ]]; then
      candidate_branches+=("main")
    fi

    local b
    for b in "${candidate_branches[@]}"; do
      local ls_out=""
      ls_out="$(git -C "$repo_root" ls-remote "$remote" "refs/heads/$b" 2>/dev/null || true)"
      [[ -z "$ls_out" ]] && continue
      local remote_sha
      remote_sha="$(awk '{print $1}' <<< "$ls_out" | head -n 1)"
      [[ -z "$remote_sha" ]] && continue

      if ! git -C "$repo_root" rev-parse --verify "$remote_sha" >/dev/null 2>&1; then
        if [[ $no_fetch -eq 0 ]]; then
          git -C "$repo_root" fetch "$remote" "$remote_sha" >/dev/null 2>&1 || \
            git -C "$repo_root" fetch "$remote" "refs/heads/$b" >/dev/null 2>&1 || true
        fi
      fi

      if ! git -C "$repo_root" rev-parse --verify "$remote_sha" >/dev/null 2>&1; then
        continue
      fi

      if git -C "$repo_root" merge-base --is-ancestor "$prereg_commit" "$remote_sha" 2>/dev/null; then
        matched_ref="$remote/$b"
        break
      fi
    done

    if [[ -z "$matched_ref" ]]; then
      echo "ERROR: prereg commit $prereg_commit is not reachable from pushed remote branch" >&2
      echo "Checked remote branches on $remote: ${candidate_branches[*]}" >&2
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
