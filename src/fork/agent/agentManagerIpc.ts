/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

// [FORK] IPC channel definition for Agent Manager window
// Used by both electron-main (app.ts) and renderer (command handler)


export const AGENT_MANAGER_CHANNEL = 'vscode:openAgentManager';

export interface IAgentManagerWindowConfig {
	backendUrl: string;   // e.g. http://localhost:3001
	wsUrl: string;        // e.g. ws://localhost:3001
	theme: 'dark';
}
