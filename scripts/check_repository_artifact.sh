#!/usr/bin/env bash
set -euo pipefail

echo "Repository size:"
du -sh .

echo
echo "Forbidden filename check:"
find . \
  -path './.git' -prune -o \
  \( -name 'node_modules' -o -name '.venv' -o -name '__pycache__' -o -name '.DS_Store' -o -name '*.pem' -o -name '.env' -o -name '*.pdf' \) \
  -print

echo
echo "Secret-pattern scan candidates:"
grep -RInE 'BEGIN (RSA|OPENSSH|PRIVATE) KEY|IBM_QUANTUM_TOKEN=.*[A-Za-z0-9_-]{20,}|QISKIT_IBM_TOKEN=.*[A-Za-z0-9_-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9_-]{20,}|mnemonic[[:space:]]*[:=]' . \
  --exclude-dir=.git \
  --exclude=package-lock.json || true

echo
echo "Git status:"
git status --short
