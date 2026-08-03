#!/usr/bin/env bash
# Skobal one-command installer / updater.
#   Install:  curl -fsSL https://raw.githubusercontent.com/GitPersonAli/skobal/main/install.sh | bash
#   Update:   rerun the same command (or: ~/.skobal/skillctl update --profile personal)
# Overrides: SKOBAL_DIR (default ~/.skobal), SKOBAL_PROFILE (default personal), SKOBAL_REPO (fork URL)
set -euo pipefail

REPO_URL="${SKOBAL_REPO:-https://github.com/GitPersonAli/skobal.git}"
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

if [ -d "$SKOBAL_DIR/.git" ]; then
  say "existing checkout at $SKOBAL_DIR — running safe update"
  cd "$SKOBAL_DIR"
  "$PY" skillctl update --profile "$PROFILE"
else
  say "cloning $REPO_URL -> $SKOBAL_DIR"
  git clone --quiet "$REPO_URL" "$SKOBAL_DIR"
  cd "$SKOBAL_DIR"
  "$PY" skillctl validate
  "$PY" skillctl sync --profile "$PROFILE"
fi

"$PY" skillctl status --profile "$PROFILE" || true
say "done — profile '$PROFILE' is installed. Rerun this script anytime to update."
