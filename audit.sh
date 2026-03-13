ls -la /workspace
ls -la /workspace/orion 2>/dev/null || echo "NO orion/ folder found"

cd /workspace && git log --oneline -10

git status

cd /workspace && python -m orion.main &
sleep 3
curl -s http://localhost:8321/health || echo "HEALTH CHECK FAILED"
curl -s http://localhost:8321/health/detailed || echo "DETAILED HEALTH FAILED"
kill %1 2>/dev/null

find /workspace/src -type f -name "*.tsx" | grep -i "orion|agent|chat|panel|webview" | head -30

find /workspace/src -type f -name "OrionStateContext*" 2>/dev/null || echo "OrionStateContext NOT FOUND"

find /workspace -path "*/contrib/orion*" -type f | head -20

find /workspace/src -type f -name "*.ts" -o -name "*.tsx" | xargs grep -l "Build with Agent\|Default Approvals\|orion:agentChannel" 2>/dev/null | head -10

cat /workspace/package.json 2>/dev/null | grep -E '"name"|"version"|"description"' | head -5

ls /workspace/orion/pipeline/components/ 2>/dev/null || echo "NO components folder"
ls /workspace/orion/api/ 2>/dev/null || echo "NO api folder"

python -c "from orion.pipeline.runner import PipelineRunner; print('PipelineRunner OK')" 2>&1
python -c "from orion.api.ws import WebSocketSessionManager; print('WebSocket OK')" 2>&1
