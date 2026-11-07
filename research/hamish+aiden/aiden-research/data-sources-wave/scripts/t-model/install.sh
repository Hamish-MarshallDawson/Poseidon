#!/bin/bash
set -x
W=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave
cd $W/data/t-model/rslearn_projects
uv pip install --python $W/venv-t-model/bin/python -r requirements.txt
echo "PIP_EXIT=$?"
