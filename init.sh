#!/usr/bin/env bash
set -euo pipefail

# autoresearch init — reads lab.yaml, generates session files, creates branch.
# Run this from your project directory with lab.yaml present.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=false

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h)
            echo "Usage: init.sh [--dry-run] [lab.yaml]"
            echo ""
            echo "  --dry-run   Validate config and show what would be generated, without writing files"
            echo "  lab.yaml    Path to config file (default: lab.yaml)"
            exit 0
            ;;
        *) CONFIG="$1"; shift ;;
    esac
done

CONFIG="${CONFIG:-lab.yaml}"

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

# Check for dirty working tree
if [[ "$DRY_RUN" == false ]] && ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "Error: working tree has uncommitted changes. Commit or stash them first." >&2
    echo "  git stash     # to stash changes" >&2
    echo "  git status    # to see what's dirty" >&2
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
METRIC_NAME=$(echo "$CONFIG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['metric']['name'])")
METRIC_DIR=$(echo "$CONFIG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['metric']['direction'])")
DATE=$(date +%Y%m%d)
BRANCH="autoresearch/${NAME}-${DATE}"

# Check that eval command includes METRIC output
EVAL_CMD=$(echo "$CONFIG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['eval'])")
if ! echo "$EVAL_CMD" | grep -q "METRIC "; then
    echo ""
    echo "Warning: your eval command does not appear to output a METRIC line." >&2
    echo "benchmark.sh expects output like: METRIC ${METRIC_NAME}=<number>" >&2
    echo "Add an echo to the end of your eval block, e.g.:" >&2
    echo "  eval: |" >&2
    echo "    your-command 2>&1" >&2
    echo "    echo \"METRIC ${METRIC_NAME}=\$(parse result here)\"" >&2
    echo "" >&2
    if [[ "$DRY_RUN" == true ]]; then
        exit 1
    fi
    read -r -p "Continue anyway? [y/N] " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "Config valid. Would generate:"
    echo "  Branch:     $BRANCH"
    echo "  Metric:     $METRIC_NAME ($METRIC_DIR is better)"
    echo "  Files:"
    echo "    program.md          — agent instructions"
    echo "    benchmark.sh        — eval harness"
    echo "    autoresearch.md     — living session document"
    echo "    results.tsv         — experiment log"
    echo "    autoresearch.ideas.md — ideas backlog"
    exit 0
fi

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
