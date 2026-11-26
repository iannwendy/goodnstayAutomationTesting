#!/usr/bin/env bash
# One-command setup & regression healthcheck for agent_automationTesting
# Verifies Python 3, lxml/Pillow, all 3 skill unit test suites, strict suite validation, and Jira env status (never printing secrets).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== 1. Python & Dependency Check ==="
python3 --version
python3 -c "import lxml, PIL; print(f'lxml={lxml.__version__}, Pillow={PIL.__version__}')"

echo ""
echo "=== 2. Running Skill Unit Tests (python3 -W error) ==="
python3 -W error -m unittest discover -s .agents/skills/jira-bug-reporter/tests -v
python3 -W error -m unittest discover -s .agents/skills/api-qa-testing/tests -v
python3 -W error -m unittest discover -s .agents/skills/stag-autobid-seeder/tests -v

echo ""
echo "=== 3. Checking API QA Lessons & Strict Suite Validation ==="
python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py lessons >/dev/null
echo "[PASS] api_test_helper.py lessons loaded cleanly."
python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py validate \
  .agents/skills/api-qa-testing/examples/op1593_regv2_test_suite.json --strict
python3 .agents/skills/api-qa-testing/scripts/api_test_helper.py validate \
  examples/suites/stag_owasp_security_smoke_suite/stag_owasp_security_smoke_test_suite.json --strict

echo ""
echo "=== 4. Checking Jira Credentials Status (Secret-Safe) ==="
if [[ -f ".env.jira" ]]; then
  echo "[OK] .env.jira exists. Running connection verification (--verify)..."
  python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --verify
else
  echo "[ACTION NEEDED] .env.jira not yet created."
  echo "  -> Run: cp .env.jira.example .env.jira && chmod 600 .env.jira"
  echo "  -> Paste your Atlassian API Token, then run:"
  echo "     python3 .agents/skills/jira-bug-reporter/scripts/jira_bug_reporter.py --verify"
fi

echo ""
echo "=== ALL AUTOMATED QA SETUP CHECKS COMPLETED ==="
