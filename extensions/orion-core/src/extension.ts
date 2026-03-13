/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import * as vscode from 'vscode';
import * as crypto from 'crypto';

const BACKEND_URL = 'http://localhost:8321';
const WS_URL = 'ws://localhost:8321';

function generateSessionId(): string {
  return crypto.randomUUID();
}

const SESSION_ID = generateSessionId();

async function runPipeline(
  prompt: string,
  mode: 'fast' | 'planning',
  stream: vscode.ChatResponseStream,
  token: vscode.CancellationToken
): Promise<void> {
  const workspacePath =
    vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? 'default';

  // 1. Trigger pipeline via REST
  let runId: string;
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
    const data = await res.json() as { run_id: string };
    runId = data.run_id;
  } catch (err) {
    stream.markdown(`❌ Could not reach Orion backend at \`${BACKEND_URL}\`. Is it running?`);
    return;
  }

  stream.progress(`Orion pipeline started (${mode} mode) · run ${runId.slice(0, 8)}`);

  // 2. Connect WebSocket to receive streaming events
  await new Promise<void>((resolve) => {
    const ws = new (require('ws'))(`${WS_URL}/ws/${SESSION_ID}`);

    token.onCancellationRequested(() => {
      ws.send(JSON.stringify({ type: 'cancel_run', run_id: runId }));
      ws.close();
      resolve();
    });

    ws.on('message', (raw: Buffer) => {
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        return;
      }

      const type = msg.type as string;

      if (type === 'pipeline.started') {
        // already shown progress above
      } else if (type === 'component.started') {
        stream.progress(`Running ${msg.component_id ?? 'component'}…`);
      } else if (type === 'text_delta') {
        stream.markdown(String(msg.content ?? ''));
      } else if (type === 'pipeline.completed') {
        stream.markdown('\n\n✅ **Orion pipeline complete.**');
        ws.close();
        resolve();
      } else if (type === 'pipeline.failed') {
        stream.markdown(`\n\n❌ **Pipeline failed:** ${msg.error}`);
        ws.close();
        resolve();
      } else if (type === 'pipeline.cancelled') {
        stream.markdown('\n\n⏹ Pipeline cancelled.');
        ws.close();
        resolve();
      } else if (type === 'approval_required') {
        stream.markdown(
          `\n\n⏸ **Approval required:** ${msg.description ?? ''}\n` +
          `Reply \`/approve\` or \`/reject\` to continue.`
        );
      } else if (type === 'skill.conflict_warning') {
        stream.markdown(`\n\n⚠️ **Skill conflict:** ${msg.warning ?? ''}`);
      } else if (type === 'error') {
        const code = msg.code as string;
        if (code === 'NO_PROVIDER_CONFIGURED') {
          stream.markdown('⚠️ No LLM provider configured. Open Orion settings to add one.');
        } else {
          stream.markdown(`❌ Error: ${code}`);
        }
        ws.close();
        resolve();
      }
    });

    ws.on('error', (err: Error) => {
      stream.markdown(`❌ WebSocket error: ${err.message}`);
      resolve();
    });
  });
}

export function activate(context: vscode.ExtensionContext): void {
  // Register Orion as a VS Code chat participant
  const participant = vscode.chat.createChatParticipant(
    'orion.agent',
    async (
      request: vscode.ChatRequest,
      _ctx: vscode.ChatContext,
      stream: vscode.ChatResponseStream,
      token: vscode.CancellationToken
    ) => {
      const prompt = request.prompt.trim();
      if (!prompt) {
        stream.markdown('Please describe what you want to build.');
        return;
      }

      // /plan prefix forces Planning Mode; default is Fast
      const mode: 'fast' | 'planning' =
        request.command === 'plan' ? 'planning' : 'fast';

      await runPipeline(prompt, mode, stream, token);
    }
  );

  participant.iconPath = vscode.Uri.joinPath(
    context.extensionUri,
    'assets',
    'orion-icon.png'
  );

  context.subscriptions.push(participant);
}

export function deactivate(): void {}
