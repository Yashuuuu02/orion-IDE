"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const crypto = __importStar(require("crypto"));
const BACKEND_URL = 'http://localhost:8321';
const WS_URL = 'ws://localhost:8321';
function generateSessionId() {
    return crypto.randomUUID();
}
const SESSION_ID = generateSessionId();
async function runPipeline(prompt, mode, stream, token) {
    const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? 'default';
    // 1. Trigger pipeline via REST
    let runId;
    try {
        const res = await fetch(`${BACKEND_URL}/api/v1/pipeline/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt,
                session_id: SESSION_ID,
                workspace_id: workspacePath,
                mode,
            }),
        });
        const data = await res.json();
        runId = data.run_id;
    }
    catch (err) {
        stream.markdown(`❌ Could not reach Orion backend at \`${BACKEND_URL}\`. Is it running?`);
        return;
    }
    stream.progress(`Orion pipeline started (${mode} mode) · run ${runId.slice(0, 8)}`);
    // 2. Connect WebSocket to receive streaming events
    await new Promise((resolve) => {
        const ws = new (require('ws'))(`${WS_URL}/ws/${SESSION_ID}`);
        token.onCancellationRequested(() => {
            ws.send(JSON.stringify({ type: 'cancel_run', run_id: runId }));
            ws.close();
            resolve();
        });
        ws.on('message', (raw) => {
            let msg;
            try {
                msg = JSON.parse(raw.toString());
            }
            catch {
                return;
            }
            const type = msg.type;
            if (type === 'pipeline.started') {
                // already shown progress above
            }
            else if (type === 'component.started') {
                stream.progress(`Running ${msg.component_id ?? 'component'}…`);
            }
            else if (type === 'text_delta') {
                stream.markdown(String(msg.content ?? ''));
            }
            else if (type === 'pipeline.completed') {
                stream.markdown('\n\n✅ **Orion pipeline complete.**');
                ws.close();
                resolve();
            }
            else if (type === 'pipeline.failed') {
                stream.markdown(`\n\n❌ **Pipeline failed:** ${msg.error}`);
                ws.close();
                resolve();
            }
            else if (type === 'pipeline.cancelled') {
                stream.markdown('\n\n⏹ Pipeline cancelled.');
                ws.close();
                resolve();
            }
            else if (type === 'approval_required') {
                stream.markdown(`\n\n⏸ **Approval required:** ${msg.description ?? ''}\n` +
                    `Reply \`/approve\` or \`/reject\` to continue.`);
            }
            else if (type === 'skill.conflict_warning') {
                stream.markdown(`\n\n⚠️ **Skill conflict:** ${msg.warning ?? ''}`);
            }
            else if (type === 'error') {
                const code = msg.code;
                if (code === 'NO_PROVIDER_CONFIGURED') {
                    stream.markdown('⚠️ No LLM provider configured. Open Orion settings to add one.');
                }
                else {
                    stream.markdown(`❌ Error: ${code}`);
                }
                ws.close();
                resolve();
            }
        });
        ws.on('error', (err) => {
            stream.markdown(`❌ WebSocket error: ${err.message}`);
            resolve();
        });
    });
}
function activate(context) {
    // Register Orion as a VS Code chat participant
    const participant = vscode.chat.createChatParticipant('orion.agent', async (request, _ctx, stream, token) => {
        const prompt = request.prompt.trim();
        if (!prompt) {
            stream.markdown('Please describe what you want to build.');
            return;
        }
        // /plan prefix forces Planning Mode; default is Fast
        const mode = request.command === 'plan' ? 'planning' : 'fast';
        await runPipeline(prompt, mode, stream, token);
    });
    participant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'assets', 'orion-icon.png');
    context.subscriptions.push(participant);
}
function deactivate() { }
//# sourceMappingURL=extension.js.map