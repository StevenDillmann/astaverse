#!/bin/bash
# Oracle path: run the hand-written reference sweep.
set -euo pipefail
cd /app
if [ ! -f /app/reference_analysis.py ]; then
  echo "no reference_analysis.py: write one to use the oracle agent" >&2
  exit 1
fi
cp /app/reference_analysis.py /app/analysis.py
python /app/analysis.py
