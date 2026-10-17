#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python analyze.py --source source --out results --download --accept-provisional-h36m
.venv/bin/python -m unittest test_analysis -v
.venv/bin/python render_gif.py
