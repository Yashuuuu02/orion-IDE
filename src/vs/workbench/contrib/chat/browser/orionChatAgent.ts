/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { CancellationToken } from '../../../../base/common/cancellation.js';
import { Disposable } from '../../../../base/common/lifecycle.js';
import { localize2 } from '../../../../nls.js';
import { IWorkbenchContribution, registerWorkbenchContribution2, WorkbenchPhase } from '../../../common/contributions.js';
import { IChatAgentImplementation, IChatAgentRequest, IChatAgentResult, IChatAgentService, IChatAgentHistoryEntry } from '../common/participants/chatAgents.js';
import { IChatProgress } from '../common/chatService/chatService.js';
import { ChatAgentLocation, ChatModeKind } from '../common/constants.js';
import { IWorkspaceContextService } from '../../../../platform/workspace/common/workspace.js';
import { IMainProcessService } from '../../../../platform/ipc/common/mainProcessService.js';

const ORION_AGENT_ID = 'orion.agent';

/** Tracks pending plan run_id for proceed/cancel */
let activePlanRunId: string | null = null;

class OrionChatAgentImplementation implements IChatAgentImplementation {
	constructor(private readonly mainProcessService: IMainProcessService) {}

	async invoke(
		request: IChatAgentRequest,
		progress: (parts: IChatProgress[]) => void,
		history: IChatAgentHistoryEntry[],
		token: CancellationToken
	): Promise<IChatAgentResult> {
		const prompt = request.message.trim();
		if (!prompt) {
			return {};
		}

		// Handle proceed/cancel for pending plan approvals
		const promptLower = prompt.toLowerCase();

		// Dynamically get the Backend port allocated by electron-main
		let orionPort = '8321';
		try {
			const orionChannel = this.mainProcessService.getChannel('orion');
			orionPort = await orionChannel.call<string>('getPort');
		} catch (e) {
			console.warn('Failed to fetch dynamic orion port from main process. Falling back to 8321.', e);
		}
		
		const ORION_BACKEND = `http://127.0.0.1:${orionPort}`;
		const ORION_WS = `ws://127.0.0.1:${orionPort}`;

		if (promptLower === 'proceed' || promptLower === 'yes' || promptLower === 'go') {
			const pendingRunId = activePlanRunId;
			if (pendingRunId) {
				activePlanRunId = null;
				try {
					await fetch(`${ORION_BACKEND}/api/v1/pipeline/approve/${pendingRunId}`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ decision: { approved: true }, approval_type: 'planner' }),
					});
				} catch {
					// Fallback: send via WebSocket
					try {
						const encoded = encodeURIComponent(request.requestId ?? 'vscode-session');
						const ws = new WebSocket(`${ORION_WS}/ws/${encoded}`);
						ws.onopen = () => {
							ws.send(JSON.stringify({
								type: 'approve_plan',
								run_id: pendingRunId,
								decision: { approved: true }
							}));
							ws.close();
						};
					} catch { /* ignore */ }
				}
				progress([{ kind: 'markdownContent', content: { value: '▶️ Executing plan...' } }]);
				return {};
			}
			progress([{ kind: 'markdownContent', content: { value: 'No pending plan to approve.' } }]);
			return {};
		}

		if (promptLower === 'cancel' || promptLower === 'no' || promptLower === 'abort') {
			const pendingRunId = activePlanRunId;
			if (pendingRunId) {
				activePlanRunId = null;
				try {
					const encoded = encodeURIComponent(request.requestId ?? 'vscode-session');
					const ws = new WebSocket(`${ORION_WS}/ws/${encoded}`);
					ws.onopen = () => {
						ws.send(JSON.stringify({
							type: 'reject_plan',
							run_id: pendingRunId,
							decision: { approved: false }
						}));
						ws.close();
					};
				} catch { /* ignore */ }
				progress([{ kind: 'markdownContent', content: { value: '⏹ Plan cancelled.' } }]);
				return {};
			}
			progress([{ kind: 'markdownContent', content: { value: 'No pending plan to cancel.' } }]);
			return {};
		}

		const mode = request.command === 'plan' ? 'planning' : 'fast';
		// Use sessionResource for a stable, per-conversation ID instead of the per-request requestId
		const sessionId = request.sessionResource?.toString() ?? request.requestId ?? 'vscode-session';
		// Dynamically resolve the workspace root via IWorkspaceContextService (injected in OrionChatAgentContribution)
		const workspaceId = OrionChatAgentContribution.resolvedWorkspaceId ?? 'default';

		// 1. Trigger pipeline via REST
		let runId: string;
		try {
			const res = await fetch(`${ORION_BACKEND}/api/v1/pipeline/run`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ prompt, session_id: sessionId, workspace_id: workspaceId, mode }),
			});
			if (!res.ok) {
				throw new Error(`HTTP ${res.status}`);
			}
			const data = await res.json() as { run_id: string; mode: string };
			runId = data.run_id;
		} catch (err) {
			progress([{
				kind: 'markdownContent',
				content: { value: `❌ Could not reach Orion backend at \`${ORION_BACKEND}\`. Is it running?\n\nError: ${err}` }
			}]);
			return { errorDetails: { message: String(err) } };
		}

		progress([{
			kind: 'markdownContent',
			content: { value: `⚡ Orion pipeline started · \`${mode}\` mode · run \`${runId.slice(0, 8)}\`\n\n` }
		}]);

		// 2. Stream events via WebSocket
		await new Promise<void>((resolve) => {
			const encoded = encodeURIComponent(sessionId);
			const wsUrl = `${ORION_WS}/ws/${encoded}`;

			let ws: WebSocket;
			try {
				ws = new WebSocket(wsUrl);
			} catch {
				progress([{ kind: 'markdownContent', content: { value: '❌ WebSocket unavailable.' } }]);
				resolve();
				return;
			}

			const cleanup = () => {
				try { cancelListener.dispose(); } catch { /* ignore */ }
				try { ws.close(); } catch { /* ignore */ }
				resolve();
			};

			const cancelListener = token.onCancellationRequested(() => {
				try {
					if (ws.readyState === WebSocket.OPEN) {
						ws.send(JSON.stringify({ type: 'cancel_run', run_id: runId }));
					}
				} catch { /* ignore */ }
				cleanup();
			});

			ws.onmessage = (event) => {
				let msg: Record<string, unknown>;
				try {
					msg = JSON.parse(event.data as string);
				} catch {
					return;
				}

				const type = msg['type'] as string;

				if (type === 'component.started') {
					// Backend emits 'component' key (from BaseComponent._ws_emit) — was incorrectly reading 'component_id'
					progress([{ kind: 'markdownContent', content: { value: `\n> ⚙️ _${msg['component']}…_\n` } }]);

				} else if (type === 'plan.ready') {
					const fileplan = (msg['file_plan'] as Array<Record<string, string>>) ?? [];
					const lines: string[] = [
						'\n---',
						`## 📋 Orion Plan`,
						`**${msg['file_count']} file operations planned**`,
						'',
					];
					for (const f of fileplan) {
						const op = f['operation'] ?? 'create';
						const icon = op === 'delete' ? '🗑️' : op === 'modify' ? '✏️' : op === 'mkdir' ? '📁' : '📄';
						lines.push(`- ${icon} \`${f['file_path']}\``);
					}
					lines.push('', `💰 Estimated cost: $${(msg['cost_estimate'] as number ?? 0).toFixed(4)}`);
					lines.push('', '**Type `proceed` to execute or `cancel` to abort.**');
					lines.push('---');
					activePlanRunId = runId;
					progress([{ kind: 'markdownContent', content: { value: lines.join('\n') } }]);

				} else if (type === 'execution.started') {
					progress([{ kind: 'markdownContent', content: { value: `\n---\n## 🚀 Executing ${msg['total_files']} file operations\n` } }]);

				} else if (type === 'file.created') {
					const fp = msg['file_path'] as string;
					const addedLines = msg['lines_added'] as number;
					const idx = msg['index'] as number;
					const total = msg['total'] as number;
					progress([{ kind: 'markdownContent', content: { value: `\n✅ **Created** \`${fp}\` · +${addedLines} lines [${idx}/${total}]` } }]);

				} else if (type === 'file.modified') {
					const fp = msg['file_path'] as string;
					const added = msg['lines_added'] as number;
					const removed = msg['lines_removed'] as number;
					const idx = msg['index'] as number;
					const total = msg['total'] as number;
					progress([{ kind: 'markdownContent', content: { value: `\n✏️ **Modified** \`${fp}\` · +${added} -${removed} lines [${idx}/${total}]` } }]);

				} else if (type === 'file.deleted') {
					const fp = msg['file_path'] as string;
					const removed = msg['lines_removed'] as number;
					const idx = msg['index'] as number;
					const total = msg['total'] as number;
					progress([{ kind: 'markdownContent', content: { value: `\n🗑️ **Deleted** \`${fp}\` · -${removed} lines [${idx}/${total}]` } }]);

				} else if (type === 'folder.created') {
					const fp = msg['file_path'] as string;
					const idx = msg['index'] as number;
					const total = msg['total'] as number;
					progress([{ kind: 'markdownContent', content: { value: `\n📁 **Created folder** \`${fp}\` [${idx}/${total}]` } }]);

				} else if (type === 'file.error') {
					progress([{ kind: 'markdownContent', content: { value: `\n⚠️ **Error on** \`${msg['file_path']}\`: ${msg['error']}` } }]);

				} else if (type === 'execution.complete') {
					progress([{ kind: 'markdownContent', content: { value: `\n---\n✅ **Done.** ${msg['files_written']}/${msg['total']} files written.` } }]);
					cleanup();

				} else if (type === 'text_delta') {
					progress([{ kind: 'markdownContent', content: { value: String(msg['content'] ?? '') } }]);

				} else if (type === 'pipeline.completed') {
					progress([{ kind: 'markdownContent', content: { value: '\n\n✅ **Orion pipeline complete.**' } }]);
					cleanup();

				} else if (type === 'pipeline.failed') {
					progress([{ kind: 'markdownContent', content: { value: `\n\n❌ **Pipeline failed:** ${msg['error']}` } }]);
					cleanup();

				} else if (type === 'pipeline.cancelled') {
					progress([{ kind: 'markdownContent', content: { value: '\n\n⏹ Pipeline cancelled.' } }]);
					cleanup();

				} else if (type === 'approval_required') {
					progress([{ kind: 'markdownContent', content: { value: `\n\n⏸ **Approval required:** ${msg['description'] ?? ''}\nReply \`/approve\` or \`/reject\` to continue.` } }]);

				} else if (type === 'skill.conflict_warning') {
					progress([{ kind: 'markdownContent', content: { value: `\n\n⚠️ **Skill conflict:** ${msg['warning'] ?? ''}` } }]);

				} else if (type === 'error') {
					const code = msg['code'] as string;
					const errMsg = code === 'NO_PROVIDER_CONFIGURED'
						? '⚠️ No LLM provider configured. Open Orion settings to add one.'
						: `❌ Error: ${code}`;
					progress([{ kind: 'markdownContent', content: { value: errMsg } }]);
					cleanup();
				}
			};

			ws.onerror = () => {
				progress([{ kind: 'markdownContent', content: { value: '❌ WebSocket connection failed.' } }]);
				cleanup();
			};
		});

		return {};
	}
}

export class OrionChatAgentContribution extends Disposable implements IWorkbenchContribution {
	static readonly ID = 'workbench.contrib.orionChatAgent';
	/** Shared workspace root path, set at construction time and read by OrionChatAgentImplementation.invoke() */
	static resolvedWorkspaceId: string = 'default';

	constructor(
		@IChatAgentService private readonly chatAgentService: IChatAgentService,
		@IWorkspaceContextService workspaceContextService: IWorkspaceContextService,
		@IMainProcessService mainProcessService: IMainProcessService
	) {
		super();

		// Resolve workspace root once at construction — DI-injected service, not hardcoded
		const folders = workspaceContextService.getWorkspace().folders;
		if (folders.length > 0) {
			OrionChatAgentContribution.resolvedWorkspaceId = folders[0].uri.fsPath;
		}

		this._register(this.chatAgentService.registerAgent(ORION_AGENT_ID, {
			id: ORION_AGENT_ID,
			name: 'orion',
			fullName: 'Orion Pipeline',
			description: localize2('orionAgent.description', 'Deterministic AI pipeline for OrionIDE').value,
			extensionId: { value: 'orion.orion-core', _lower: 'orion.orion-core' },
			extensionVersion: '1.0.0',
			extensionDisplayName: 'Orion Core',
			extensionPublisherId: 'orion-ide',
			publisherDisplayName: 'Orion IDE',
			isDefault: true,
			isCore: true,
			locations: [ChatAgentLocation.Chat],
			modes: [ChatModeKind.Agent, ChatModeKind.Ask, ChatModeKind.Edit],
			slashCommands: [
				{ name: 'plan', description: 'Run full 15-component Planning Mode' },
				{ name: 'fast', description: 'Run 7-component Fast Mode' },
			],
			disambiguation: [],
			metadata: { isSticky: false },
		}));

		this._register(this.chatAgentService.registerAgentImplementation(
			ORION_AGENT_ID,
			new OrionChatAgentImplementation(mainProcessService)
		));
	}
}

registerWorkbenchContribution2(
	OrionChatAgentContribution.ID,
	OrionChatAgentContribution,
	WorkbenchPhase.BlockRestore
);
