#!/bin/bash
echo "STEP 1 — Repo structure"
ls -la /workspace 2>/dev/null || ls -la ~/orion-IDE 2>/dev/null || ls -la . && pwd

echo "STEP 2 — Git log and status"
git log --oneline -10
git status

echo "STEP 3 — Backend health"
python -m orion.main &
sleep 3
curl -s http://localhost:8321/health || echo "HEALTH FAILED on 8321"
curl -s http://localhost:8000/health || echo "HEALTH FAILED on 8000"
kill %1 2>/dev/null

echo "STEP 4 — Does our webview exist"
find . -type f -name "OrionStateContext*" 2>/dev/null || echo "OrionStateContext NOT FOUND"
find . -path "*/contrib/orion*" -type f 2>/dev/null | head -20 || echo "contrib/orion NOT FOUND"
find . -type f -name "*.tsx" | xargs grep -l "AgentTab\|ChatTab\|MemorySkills" 2>/dev/null | head -10 || echo "NO TAB FILES FOUND"

echo "STEP 5 — What is the right panel"
find . -type f \( -name "*.ts" -o -name "*.tsx" \) | xargs grep -l "Build with Agent\|Default Approvals" 2>/dev/null | head -10 || echo "NOT FOUND IN CODEBASE"
cat package.json | grep -E '"name"|"version"|"description"'

echo "STEP 6 — Backend components"
ls orion/pipeline/components/ 2>/dev/null || echo "NO components folder"
ls orion/api/ 2>/dev/null || echo "NO api folder"
python -c "from orion.pipeline.runner import PipelineRunner; print('PipelineRunner OK')" 2>&1
python -c "from orion.api.ws import WebSocketSessionManager; print('WS OK')" 2>&1
