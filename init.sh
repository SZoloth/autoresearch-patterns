#!/usr/bin/env bash
set -euo pipefail

# autoresearch init — reads lab.yaml, generates session files, creates branch.
# Run this from your project directory with lab.yaml present.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find lab.yaml
CONFIG="${1:-lab.yaml}"
if [[ ! -f "$CONFIG" ]]; then
    echo "Error: $CONFIG not found. Create a lab.yaml in your project root." >&2
    echo "See examples at: $SCRIPT_DIR/examples/" >&2
    exit 1
fi

# Check for Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found." >&2
    exit 1
fi

# Check for git
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Error: not inside a git repository." >&2
    exit 1
fi

echo "Parsing $CONFIG..."

# Parse config to JSON
CONFIG_JSON=$(python3 "$SCRIPT_DIR/lib/parse_config.py" "$CONFIG")
if [[ -z "$CONFIG_JSON" ]]; then
    echo "Error: failed to parse $CONFIG" >&2
    exit 1
fi

# Extract values
NAME=$(echo "$CONFIG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['name'])")
DATE=$(date +%Y%m%d)
BRANCH="autoresearch/${NAME}-${DATE}"

# Write config JSON to temp file for renderer
TMPCONFIG=$(mktemp)
echo "$CONFIG_JSON" > "$TMPCONFIG"
trap 'rm -f "$TMPCONFIG"' EXIT

echo "Generating session files..."

# Render templates
python3 "$SCRIPT_DIR/lib/render.py" "$SCRIPT_DIR/templates/program.md.tmpl" "$TMPCONFIG" > program.md
python3 "$SCRIPT_DIR/lib/render.py" "$SCRIPT_DIR/templates/benchmark.sh.tmpl" "$TMPCONFIG" > benchmark.sh
python3 "$SCRIPT_DIR/lib/render.py" "$SCRIPT_DIR/templates/session.md.tmpl" "$TMPCONFIG" > autoresearch.md

chmod +x benchmark.sh

# Extract metric name for TSV header
METRIC_NAME=$(echo "$CONFIG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['metric']['name'])")

# Create results.tsv with header
printf "commit\t%s\tstatus\tdescription\n" "$METRIC_NAME" > results.tsv

# Create empty ideas backlog
touch autoresearch.ideas.md

echo "Creating branch: $BRANCH"

# Create branch (fail gracefully if it exists)
if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    echo "Warning: branch $BRANCH already exists. Switching to it." >&2
    git checkout "$BRANCH"
else
    git checkout -b "$BRANCH"
fi

# Stage and commit generated files
git add program.md benchmark.sh autoresearch.md results.tsv autoresearch.ideas.md
git commit -m "autoresearch: initialize ${NAME} session"

echo ""
echo "Session initialized. Generated files:"
echo "  program.md          — agent instructions"
echo "  benchmark.sh        — eval harness"
echo "  autoresearch.md     — living session document"
echo "  results.tsv         — experiment log"
echo "  autoresearch.ideas.md — ideas backlog"
echo ""
echo "Branch: $BRANCH"
echo ""
echo "Start an agent:"
echo '  claude "Read program.md and follow the instructions exactly."'
echo '  cursor   # open program.md, tell the agent to follow it'
echo '  codex    # same approach — any agent works'
