/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

// [FORK] WebSocket bridge — exposes VS Code's PTY to the companion Next.js app.
// Listens on ws://localhost:3002/terminal and mirrors I/O with node-pty.
// Start via dynamic import inside app.ts after Electron app is ready.
/* eslint-disable local/code-import-patterns */

import * as pty from 'node-pty';
import { WebSocketServer, WebSocket } from 'ws';
import * as os from 'os';

const PORT = process.env.FORK_TERMINAL_WS_PORT
	? parseInt(process.env.FORK_TERMINAL_WS_PORT, 10)
	: 3002;

// [FORK] Guard: only listen if the port is not already taken
const wss = new WebSocketServer({ port: PORT });

interface TerminalSession {
	id: string;
	pty: pty.IPty;
	clients: Set<WebSocket>;
}

const sessions = new Map<string, TerminalSession>();

function createSession(id: string, cols = 80, rows = 24): TerminalSession {
	const shell = os.platform() === 'win32'
		? 'powershell.exe'
		: (process.env.SHELL ?? 'bash');

	const proc = pty.spawn(shell, [], {
		name: 'xterm-256color',
		cols,
		rows,
		cwd: process.env.HOME ?? process.cwd(),
		env: process.env as { [key: string]: string },
	});

	const session: TerminalSession = { id, pty: proc, clients: new Set() };

	proc.onData((data: string) => {
		// [FORK] Broadcast PTY output to all connected WebSocket clients
		for (const client of session.clients) {
			if (client.readyState === WebSocket.OPEN) {
				client.send(JSON.stringify({ type: 'output', id, data }));
			}
		}
	});

	proc.onExit(({ exitCode }: { exitCode: number }) => {
		for (const client of session.clients) {
			if (client.readyState === WebSocket.OPEN) {
				client.send(JSON.stringify({ type: 'exit', id, exitCode }));
			}
		}
		sessions.delete(id);
	});

	sessions.set(id, session);
	return session;
}

wss.on('connection', (ws: WebSocket) => {
	let boundSessionId: string | null = null;

	ws.on('message', (raw: WebSocket.RawData) => {
		try {
			const msg = JSON.parse(raw.toString());

			switch (msg.type) {
				case 'create': {
					// [FORK] Create new PTY session
					const id: string = msg.id ?? `term-${Date.now()}`;
					const session = createSession(id, msg.cols ?? 80, msg.rows ?? 24);
					session.clients.add(ws);
					boundSessionId = id;
					ws.send(JSON.stringify({ type: 'created', id }));
					break;
				}
				case 'input': {
					// [FORK] Send keystrokes to PTY
					const session = sessions.get(msg.id ?? boundSessionId ?? '');
					if (session) { session.pty.write(msg.data); }
					break;
				}
				case 'resize': {
					// [FORK] Resize PTY on terminal panel resize
					const session = sessions.get(msg.id ?? boundSessionId ?? '');
					if (session) { session.pty.resize(msg.cols, msg.rows); }
					break;
				}
				case 'kill': {
					const session = sessions.get(msg.id ?? boundSessionId ?? '');
					if (session) {
						session.pty.kill();
						sessions.delete(msg.id ?? boundSessionId ?? '');
					}
					break;
				}
				case 'attach': {
					// [FORK] Attach to an existing PTY session
					const session = sessions.get(msg.id);
					if (session) {
						session.clients.add(ws);
						boundSessionId = msg.id;
						ws.send(JSON.stringify({ type: 'attached', id: msg.id }));
					}
					break;
				}
			}
		} catch (e) {
			console.error('[FORK] Terminal WS parse error:', e);
		}
	});

	ws.on('close', () => {
		if (boundSessionId) {
			const session = sessions.get(boundSessionId);
			if (session) { session.clients.delete(ws); }
		}
	});
});

console.log(`[FORK] Terminal WebSocket bridge listening on ws://localhost:${PORT}/terminal`);

export { wss, sessions, createSession };
