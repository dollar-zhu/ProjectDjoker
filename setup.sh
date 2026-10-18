#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-pose.txt
printf '\nRun: .venv/bin/python reference/analyze.py --source reference/source --out reference/results --accept-provisional-h36m\n'
