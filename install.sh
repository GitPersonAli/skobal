#!/usr/bin/env bash
# Skobal one-command installer / updater.
#   Install:  curl -fsSL https://raw.githubusercontent.com/GitPersonAli/skobal/main/install.sh | bash
#   Update:   rerun the same command (or: ~/.skobal/skillctl update --profile personal)
# Overrides: SKOBAL_DIR (default ~/.skobal), SKOBAL_PROFILE (default personal), SKOBAL_REPO (fork URL)
set -euo pipefail

REPO_URL="${SKOBAL_REPO:-https://github.com/GitPersonAli/skobal.git}"
SKOBAL_DIR_EXPLICIT="${SKOBAL_DIR:+yes}"
SKOBAL_DIR="${SKOBAL_DIR:-$HOME/.skobal}"
PROFILE="${SKOBAL_PROFILE:-personal}"

say() { printf '[skobal] %s\n' "$*"; }
die() { printf '[skobal] error: %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required"
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || die "Python 3.10+ is required"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python 3.10+ is required (found: $("$PY" -V 2>&1))"

if ! "$PY" -c 'import yaml' >/dev/null 2>&1; then
  say "installing PyYAML"
  "$PY" -m pip install --user PyYAML >/dev/null 2>&1 \
    || "$PY" -m pip install PyYAML >/dev/null 2>&1 \
    || die "could not install PyYAML; install it with your package manager (e.g. apt install python3-yaml) and rerun"
fi

# Find a checkout (other than SKOBAL_DIR) that already manages skills here —
# its symlinks reveal the source.
find_foreign_owner() {
  for link in "$HOME/.claude/skills"/*; do
    [ -L "$link" ] || continue
    target="$(readlink "$link")" || continue
    candidate="${target%/skills/*}"
    if [ -d "$candidate/.git" ] && [ -f "$candidate/skillctl" ] \
       && [ "$candidate" != "$SKOBAL_DIR" ]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -z "$SKOBAL_DIR_EXPLICIT" ]; then
  # No explicit choice: always follow the checkout that actually manages the
  # skills (a stale default-path clone must not shadow a migrated install).
  if owner="$(find_foreign_owner)"; then
    say "skills already managed from $owner — updating that checkout instead"
    say "(to force a separate install, rerun with SKOBAL_DIR=/some/other/path)"
    SKOBAL_DIR="$owner"
  fi
elif [ -n "$SKOBAL_DIR_EXPLICIT" ] && owner="$(find_foreign_owner)"; then
  # Explicit choice while another checkout owns the skills: migrate or explain.
  if [ "${SKOBAL_MIGRATE:-}" = "1" ]; then
    say "migrating management: $owner -> $SKOBAL_DIR"
    for link in "$HOME/.claude/skills"/*; do
      [ -L "$link" ] || continue
      case "$(readlink "$link")" in "$owner"/*) rm "$link"; say "released $(basename "$link")";; esac
    done
    say "old checkout left on disk at $owner — delete it yourself when ready"
  else
    cat >&2 <<EOF
[skobal] error: skills here are managed from another checkout: $owner
[skobal] You asked for a new install at $SKOBAL_DIR. Pick one:
[skobal]   - migrate management to $SKOBAL_DIR: rerun with SKOBAL_MIGRATE=1
[skobal]   - or keep the existing install:      cd $owner && ./skillctl update
EOF
    exit 1
  fi
fi

sync_hint() {
  cat >&2 <<'HINT'
[skobal] sync refused (see error above). Most common cause: another skobal
[skobal] checkout already manages these skills. Fix one of:
[skobal]   - rerun with SKOBAL_DIR=<that checkout>  (updates it in place)
[skobal]   - or retire the old checkout: remove its symlinks from the skills
[skobal]     directory, then rerun this installer
HINT
  exit 1
}

if [ -d "$SKOBAL_DIR/.git" ]; then
  say "existing checkout at $SKOBAL_DIR — running safe update"
  cd "$SKOBAL_DIR"
  "$PY" skillctl update --profile "$PROFILE" || sync_hint
else
  say "cloning $REPO_URL -> $SKOBAL_DIR"
  git clone --quiet "$REPO_URL" "$SKOBAL_DIR"
  cd "$SKOBAL_DIR"
  "$PY" skillctl validate
  "$PY" skillctl sync --profile "$PROFILE" || sync_hint
fi

"$PY" skillctl status --profile "$PROFILE" || true
say "done — profile '$PROFILE' is installed. Rerun this script anytime to update."
