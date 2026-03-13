import os
import re
import json
import ast

EXCLUDES = {'node_modules', '.git', '__pycache__', 'out', 'out-build', 'out-vscode', 'build', 'target'}

def filter_dirs(dirs):
    return [d for d in dirs if d not in EXCLUDES]

out_path = r"c:\Users\Shreyash\.gemini\antigravity\brain\3a573891-66c0-406f-8a50-f347067453a1\orion_audit_report.md"

with open(out_path, "w", encoding="utf-8") as out:

    def pr(text):
        out.write(text + "\n")

    pr("# 1. DIRECTORY STRUCTURE")
    py_files = []
    ts_files = []
    print('Generating audit report...')
    
    for root, dirs, files in os.walk("."):
        dirs[:] = filter_dirs(dirs)
        for f in files:
            p = os.path.normpath(os.path.join(root, f)).replace('\\', '/')
            if f.endswith(".py"):
                py_files.append(p)
            elif f.endswith(".ts") or f.endswith(".tsx"):
                ts_files.append(p)
                
    py_files.sort()
    ts_files.sort()
    
    pr("## Python files")
    for p in py_files: pr(p)
        
    pr("\n## TypeScript files")
    for p in ts_files: pr(p)
    
    pr("\n---\n")
    pr("# 2. FASTAPI ROUTES")
    route_re = re.compile(r"@(app|router)\.(get|post|websocket)")
    for p in py_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if route_re.search(line):
                        pr(f"File: {p}")
                        pr(f"Decorator: {line.strip()}")
                        for j in range(i+1, min(i+10, len(lines))):
                            if lines[j].strip().startswith("def ") or lines[j].strip().startswith("async def "):
                                pr(f"Function: {lines[j].strip()}\n")
                                break
        except Exception as e:
            pr(f"Error analyzing {p}: {e}")

    pr("\n---\n")
    pr("# 3. WEBSOCKET HANDLER")
    found_ws = False
    for p in py_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                if "class WebSocketSessionManager" in content:
                    found_ws = True
                    pr(f"File: {p}")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef) and node.name == "WebSocketSessionManager":
                            code_lines = content.splitlines()
                            pr("\n".join(code_lines[node.lineno-1:node.end_lineno]))
                            break
        except:
            pass
    if not found_ws:
        pr("Not found.")

    pr("\n---\n")
    pr("# 4. PIPELINE RUNNER")
    found_runner = False
    for p in py_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                if "class PipelineRunner" in content:
                    found_runner = True
                    pr(f"File: {p}")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef) and node.name == "PipelineRunner":
                            for child in node.body:
                                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    if not child.name.startswith("_") or child.name == "__init__":
                                        code_lines = content.splitlines()
                                        sig = []
                                        for i in range(child.lineno-1, len(code_lines)):
                                            sig.append(code_lines[i].strip())
                                            if code_lines[i].rstrip().endswith(':'):
                                                break
                                        pr(" ".join(sig))
                    
                    lines = content.splitlines()
                    regs = []
                    in_list = False
                    for l in lines:
                        if "PLANNING_MODE_COMPONENTS" in l or "FAST_MODE_COMPONENTS" in l or "planning_registry" in l or "fast_registry" in l:
                            in_list = True
                        if in_list:
                            regs.append(l)
                            if "]" in l:
                                in_list = False
                    pr("\nRegistries:")
                    pr("\n".join(regs))
        except:
            pass
    if not found_runner:
        pr("Not found.")

    pr("\n---\n")
    pr("# 5. EXTENSION ENTRY POINT")
    found_ext = False
    for p in ts_files:
        if p.endswith("extension.ts") or p.endswith("extension.js") or p.endswith("main.ts"):
            # Limit printing massive VS Code files unless it's the actual extension
            pass
            # Instead of guessing, we'll try to find any small extension.ts
            if 'extension' in p.lower():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        content = f.read()
                        if 'activate' in content:
                            found_ext = True
                            pr(f"\nFile: {p}")
                            pr(content[:2000] + "\n... (truncated for size)")
                except:
                    pass
    if not found_ext:
        pr("Not found.")
                
    pr("\n---\n")
    pr("# 6. PACKAGE.JSON CONTRIBUTES")
    for dir_path in [".", "orion"]:
        pkg = os.path.normpath(os.path.join(dir_path, "package.json")).replace('\\', '/')
        if os.path.exists(pkg):
            try:
                with open(pkg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "contributes" in data or "activationEvents" in data:
                        pr(f"File: {pkg}")
                        pr("contributes:")
                        pr(json.dumps(data.get("contributes", {}), indent=2))
                        pr("\nactivationEvents:")
                        pr(json.dumps(data.get("activationEvents", []), indent=2))
                        break
            except:
                pass
                
    pr("\n---\n")
    pr("# 7. EXISTING CHAT / WEBVIEW WIRING")
    search_strs = ["chatParticipants", "vscode.chat", "postMessage", "acquireVsCodeApi", "pipeline/run", "ws://localhost", "8321"]
    all_files = py_files + ts_files
    for root, dirs, files in os.walk("."):
        dirs[:] = filter_dirs(dirs)
        for f in files:
            if f.endswith(".json") or f.endswith(".js"):
                all_files.append(os.path.normpath(os.path.join(root, f)).replace('\\', '/'))

    for p in all_files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    for s in search_strs:
                        if s in line:
                            pr(f"{p}:{i+1}: {line.strip()}")
                            break
        except:
            pass
            
    pr("\n---\n")
    pr("# 8. FRONTEND CHAT COMPONENT")
    for p in ts_files:
        # Match Chat.tsx, ChatTab.tsx, or anything strongly related to chat
        name = os.path.basename(p)
        if "chat" in name.lower() and (p.endswith(".tsx") or p.endswith(".ts")):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "button" in content.lower() or "input" in content.lower() or "send" in content.lower():
                        pr(f"File: {p}")
                        pr(content)
                        pr("---")
            except:
                pass

    pr("\n---\n")
    pr("# 9. BACKEND MAIN ENTRY")
    for p in py_files:
        if p.endswith("main.py") or p.endswith("app.py"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "FastAPI" in content or "uvicorn" in content:
                        pr(f"File: {p}")
                        pr(content)
            except:
                pass

print("Audit report generated successfully.")
