#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python main.py
