/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import './media/chatStatus.css';
import { Disposable, MutableDisposable } from '../../../../../base/common/lifecycle.js';
import { IWorkbenchContribution } from '../../../../common/contributions.js';
import { ChatEntitlementService, IChatEntitlementService } from '../../../../services/chat/common/chatEntitlementService.js';
import { IEditorService } from '../../../../services/editor/common/editorService.js';
import { getCodeEditor } from '../../../../../editor/browser/editorBrowser.js';
import { IInlineCompletionsService } from '../../../../../editor/browser/services/inlineCompletionsService.js';
import { IChatSessionsService } from '../../common/chatSessionsService.js';

export class ChatStatusBarEntry extends Disposable implements IWorkbenchContribution {

	static readonly ID = 'workbench.contrib.chatStatusBarEntry';

	private readonly activeCodeEditorListener = this._register(new MutableDisposable());

	constructor(
		@IChatEntitlementService private readonly chatEntitlementService: ChatEntitlementService,
		@IEditorService private readonly editorService: IEditorService,
		@IInlineCompletionsService private readonly completionsService: IInlineCompletionsService,
		@IChatSessionsService private readonly chatSessionsService: IChatSessionsService,
	) {
		super();
		this.registerListeners();
	}

	private registerListeners(): void {
		this._register(this.chatEntitlementService.onDidChangeQuotaExceeded(() => { }));
		this._register(this.chatEntitlementService.onDidChangeSentiment(() => { }));
		this._register(this.chatEntitlementService.onDidChangeEntitlement(() => { }));

		this._register(this.completionsService.onDidChangeIsSnoozing(() => { }));

		this._register(this.chatSessionsService.onDidChangeInProgress(() => { }));

		this._register(this.editorService.onDidActiveEditorChange(() => this.onDidActiveEditorChange()));
	}

	private onDidActiveEditorChange(): void {
		this.activeCodeEditorListener.clear();

		const activeCodeEditor = getCodeEditor(this.editorService.activeTextEditorControl);
		if (activeCodeEditor) {
			this.activeCodeEditorListener.value = activeCodeEditor.onDidChangeModelLanguage(() => { });
		}
	}
}
