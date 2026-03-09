/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import * as dom from '../../../../../../base/browser/dom.js';
import { renderIcon } from '../../../../../../base/browser/ui/iconLabel/iconLabels.js';
import { raceCancellationError } from '../../../../../../base/common/async.js';
import { CancellationToken } from '../../../../../../base/common/cancellation.js';
import { Codicon } from '../../../../../../base/common/codicons.js';
import { ThemeIcon } from '../../../../../../base/common/themables.js';
import { URI } from '../../../../../../base/common/uri.js';
import * as nls from '../../../../../../nls.js';
import { ITextResourceConfigurationService } from '../../../../../../editor/common/services/textResourceConfiguration.js';
import { IContextKeyService, IScopedContextKeyService } from '../../../../../../platform/contextkey/common/contextkey.js';
import { IEditorOptions } from '../../../../../../platform/editor/common/editor.js';
import { IInstantiationService } from '../../../../../../platform/instantiation/common/instantiation.js';
import { ServiceCollection } from '../../../../../../platform/instantiation/common/serviceCollection.js';
import { IStorageService } from '../../../../../../platform/storage/common/storage.js';
import { ITelemetryService } from '../../../../../../platform/telemetry/common/telemetry.js';
import { editorBackground, editorForeground, inputBackground } from '../../../../../../platform/theme/common/colorRegistry.js';
import { IThemeService } from '../../../../../../platform/theme/common/themeService.js';
import { AbstractEditorWithViewState } from '../../../../../browser/parts/editor/editorWithViewState.js';
import { IEditorOpenContext } from '../../../../../common/editor.js';
import { EditorInput } from '../../../../../common/editor/editorInput.js';
import { EDITOR_DRAG_AND_DROP_BACKGROUND } from '../../../../../common/theme.js';
import { IEditorGroup, IEditorGroupsService } from '../../../../../services/editor/common/editorGroupsService.js';
import { IEditorService } from '../../../../../services/editor/common/editorService.js';
import { ChatContextKeys } from '../../../common/actions/chatContextKeys.js';
import { IChatModel, IChatModelInputState, IExportableChatData, ISerializableChatData } from '../../../common/model/chatModel.js';
import { IChatService } from '../../../common/chatService/chatService.js';
import { IChatSessionsService, localChatSessionType } from '../../../common/chatSessionsService.js';
import { ChatAgentLocation, ChatModeKind } from '../../../common/constants.js';
import { clearChatEditor } from '../../actions/chatClear.js';
import { ChatEditorInput } from './chatEditorInput.js';
import { ChatWidget } from '../../widget/chatWidget.js';

export interface IChatEditorOptions extends IEditorOptions {
	/**
	 * Input state of the model when the editor is opened. Currently needed since
	 * new sessions are not persisted but may go away with
	 * https://github.com/microsoft/vscode/pull/278476 as input state is stored on the model.
	 */
	modelInputState?: IChatModelInputState;
	target?: { data: IExportableChatData | ISerializableChatData };
	title?: {
		preferred?: string;
		fallback?: string;
	};
}

export interface IChatEditorViewState {
	scrollTop: number;
}

export class ChatEditor extends AbstractEditorWithViewState<IChatEditorViewState> {
	private static readonly VIEW_STATE_KEY = 'chatEditorViewState';

	private _widget!: ChatWidget;
	public get widget(): ChatWidget {
		return this._widget;
	}
	private _scopedContextKeyService!: IScopedContextKeyService;
	override get scopedContextKeyService() {
		return this._scopedContextKeyService;
	}

	private dimension = new dom.Dimension(0, 0);
	private _loadingContainer: HTMLElement | undefined;
	private _editorContainer: HTMLElement | undefined;

	constructor(
		group: IEditorGroup,
		@ITelemetryService telemetryService: ITelemetryService,
		@IThemeService themeService: IThemeService,
		@IInstantiationService instantiationService: IInstantiationService,
		@IStorageService storageService: IStorageService,
		@IChatSessionsService private readonly chatSessionsService: IChatSessionsService,
		@IContextKeyService private readonly contextKeyService: IContextKeyService,
		@IChatService private readonly chatService: IChatService,
		@ITextResourceConfigurationService textResourceConfigurationService: ITextResourceConfigurationService,
		@IEditorService editorService: IEditorService,
		@IEditorGroupsService editorGroupService: IEditorGroupsService,
	) {
		super(ChatEditorInput.EditorID, group, ChatEditor.VIEW_STATE_KEY, telemetryService, instantiationService, storageService, textResourceConfigurationService, themeService, editorService, editorGroupService);
	}

	private async clear() {
		if (this.input) {
			return this.instantiationService.invokeFunction(clearChatEditor, this.input as ChatEditorInput);
		}
	}

	protected override createEditor(parent: HTMLElement): void {
		this._editorContainer = parent;
		// Ensure the container has position relative for the loading overlay
		parent.classList.add('chat-editor-relative');
		this._scopedContextKeyService = this._register(this.contextKeyService.createScoped(parent));
		const scopedInstantiationService = this._register(this.instantiationService.createChild(new ServiceCollection([IContextKeyService, this.scopedContextKeyService])));
		ChatContextKeys.inChatEditor.bindTo(this._scopedContextKeyService).set(true);

		// [FORK] OrionIDE - Pear AI Style Agent Sidebar Layout
		const wrapper = dom.$('.orion-side-agent-wrapper');
		const header = dom.$('.orion-side-agent-header');
		const toggles = dom.$('.orion-mode-toggles');

		const createToggle = (name: string, iconClass: string, isActive: boolean) => {
			const el = dom.$(`.orion-mode-toggle.${name.toLowerCase()}${isActive ? '.active' : ''}`);
			dom.append(el, dom.$(`span.icon.codicon.${iconClass}`));
			dom.append(el, dom.$('span.text', undefined, name));
			return el;
		};

		const agentToggle = createToggle('Agent', 'codicon-hubot', false);
		const chatToggle = createToggle('Chat', 'codicon-comment-discussion', true);
		const searchToggle = createToggle('Search', 'codicon-search', false);
		const memoryToggle = createToggle('Memory', 'codicon-database', false);

		dom.append(toggles, agentToggle, chatToggle, searchToggle, memoryToggle);

		const actions = dom.$('.orion-side-agent-actions');
		['codicon-add', 'codicon-history'].forEach(ic => {
			dom.append(actions, dom.$(`span.action-icon.codicon.${ic}`));
		});

		dom.append(header, toggles, actions);

		const contentArea = dom.$('.orion-side-agent-content');
		const welcomeScreen = dom.$('.orion-welcome-screen');

		const clearNode = (node: HTMLElement) => {
			while (node.firstChild) {
				node.removeChild(node.firstChild);
			}
		};

		const updateWelcome = (mode: string) => {
			clearNode(welcomeScreen);
			if (mode === 'Chat') {
				dom.append(welcomeScreen, dom.$('h2', undefined, 'OrionIDE Chat'));
				dom.append(welcomeScreen, dom.$('.subtitle', undefined, 'Powered by OrionIDE'));
				dom.append(welcomeScreen, dom.$('p', undefined, 'Ask questions about the code or make changes.'));
				const shortcuts = dom.$('.shortcuts');
				dom.append(shortcuts, dom.$('div', undefined, '⌘ + I Make inline edits'));
				dom.append(shortcuts, dom.$('div', undefined, '⌘ + L Add selection to chat'));
				dom.append(welcomeScreen, shortcuts);
			} else if (mode === 'Agent') {
				dom.append(welcomeScreen, dom.$('h2', undefined, 'OrionIDE Coding Agent'));
				dom.append(welcomeScreen, dom.$('.subtitle', undefined, 'Powered by OrionIDE'));
				dom.append(welcomeScreen, dom.$('p', undefined, 'Autonomous coding agent that has access to your development environment (with your permission) for a feedback loop to add features, fix bugs, and more.'));
				const autoApprove = dom.$('label.auto-approve');
				const cb = dom.$('input') as HTMLInputElement;
				cb.type = 'checkbox';
				cb.checked = true;
				dom.append(autoApprove, cb, dom.$('span', undefined, ' Auto-approve: Read, Write, Execute, Browser, MCP...'));
				dom.append(welcomeScreen, autoApprove);
			} else if (mode === 'Search') {
				dom.append(welcomeScreen, dom.$('h2', undefined, 'OrionIDE Search'));
				dom.append(welcomeScreen, dom.$('.subtitle', undefined, 'Powered by Perplexity'));
				dom.append(welcomeScreen, dom.$('p', undefined, 'AI-powered search engine: up-to-date information for docs, libraries, etc. Also good for non-coding specific questions.'));
			} else if (mode === 'Memory') {
				dom.append(welcomeScreen, dom.$('h2', undefined, 'OrionIDE Memory'));
				dom.append(welcomeScreen, dom.$('.subtitle', undefined, 'Local Memory Storage'));
				dom.append(welcomeScreen, dom.$('p', undefined, 'OrionIDE Memory allows you to add information for OrionIDE to remember. Add memories to personalize your building experience!'));
				dom.append(welcomeScreen, dom.$('p', undefined, 'No memories yet - Click the button below to add memories.'));
				const btn = dom.$('button.add-memory-btn', undefined, 'Add Memory');
				dom.append(welcomeScreen, btn);
			}
		};
		updateWelcome('Chat');

		const allToggles = [
			{ el: agentToggle, name: 'Agent' },
			{ el: chatToggle, name: 'Chat' },
			{ el: searchToggle, name: 'Search' },
			{ el: memoryToggle, name: 'Memory' }
		];
		allToggles.forEach(t => {
			t.el.onclick = () => {
				allToggles.forEach(x => x.el.classList.remove('active'));
				t.el.classList.add('active');
				updateWelcome(t.name);
			};
		});

		const chatWidgetContainer = dom.$('.orion-chat-widget-container');
		dom.append(contentArea, welcomeScreen, chatWidgetContainer);
		dom.append(wrapper, header, contentArea);
		dom.append(parent, wrapper);

		this._widget = this._register(
			scopedInstantiationService.createInstance(
				ChatWidget,
				ChatAgentLocation.Chat,
				undefined,
				{
					autoScroll: mode => mode !== ChatModeKind.Ask,
					renderFollowups: true,
					supportsFileReferences: true,
					clear: () => this.clear(),
					rendererOptions: {
						renderTextEditsAsSummary: (uri) => {
							return true;
						},
						referencesExpandedWhenEmptyResponse: false,
						progressMessageAtBottomOfResponse: mode => mode !== ChatModeKind.Ask,
					},
					enableImplicitContext: true,
					enableWorkingSet: 'explicit',
					supportsChangingModes: true,
				},
				{
					listForeground: editorForeground,
					listBackground: editorBackground,
					overlayBackground: EDITOR_DRAG_AND_DROP_BACKGROUND,
					inputEditorBackground: inputBackground,
					resultEditorBackground: editorBackground
				}));
		this._register(this.widget.onDidSubmitAgent(() => {
			this.group.pinEditor(this.input);
		}));
		this.widget.render(chatWidgetContainer);
		this.widget.setVisible(true);
	}

	protected override setEditorVisible(visible: boolean): void {
		super.setEditorVisible(visible);

		this.widget?.setVisible(visible);

		if (visible && this.widget) {
			this.widget.layout(this.dimension.height, this.dimension.width);
		}
	}

	public override focus(): void {
		super.focus();

		this.widget?.focusInput();
	}

	override clearInput(): void {
		this.widget.setModel(undefined);
		super.clearInput();
	}

	private showLoadingInChatWidget(message: string): void {
		if (!this._editorContainer) {
			return;
		}

		// If already showing, just update text
		if (this._loadingContainer) {
			// eslint-disable-next-line no-restricted-syntax
			const existingText = this._loadingContainer.querySelector('.chat-loading-content span');
			if (existingText) {
				existingText.textContent = message;
				return; // aria-live will announce the text change
			}
			this.hideLoadingInChatWidget(); // unexpected structure
		}

		// Mark container busy for assistive technologies
		this._editorContainer.setAttribute('aria-busy', 'true');

		this._loadingContainer = dom.append(this._editorContainer, dom.$('.chat-loading-overlay'));
		// Accessibility: announce loading state politely without stealing focus
		this._loadingContainer.setAttribute('role', 'status');
		this._loadingContainer.setAttribute('aria-live', 'polite');
		// Rely on live region text content instead of aria-label to avoid duplicate announcements
		this._loadingContainer.tabIndex = -1; // ensure it isn't focusable
		const loadingContent = dom.append(this._loadingContainer, dom.$('.chat-loading-content'));
		const spinner = renderIcon(ThemeIcon.modify(Codicon.loading, 'spin'));
		spinner.setAttribute('aria-hidden', 'true');
		loadingContent.appendChild(spinner);
		const text = dom.append(loadingContent, dom.$('span'));
		text.textContent = message;
	}

	private hideLoadingInChatWidget(): void {
		if (this._loadingContainer) {
			this._loadingContainer.remove();
			this._loadingContainer = undefined;
		}
		if (this._editorContainer) {
			this._editorContainer.removeAttribute('aria-busy');
		}
	}

	override async setInput(input: ChatEditorInput, options: IChatEditorOptions | undefined, context: IEditorOpenContext, token: CancellationToken): Promise<void> {
		// Show loading indicator early for non-local sessions to prevent layout shifts
		let isContributedChatSession = false;
		const chatSessionType = input.getSessionType();
		if (chatSessionType !== localChatSessionType) {
			const loadingMessage = nls.localize('chatEditor.loadingSession', "Loading...");
			this.showLoadingInChatWidget(loadingMessage);
		}

		await super.setInput(input, options, context, token);
		if (token.isCancellationRequested) {
			this.hideLoadingInChatWidget();
			return;
		}

		if (!this.widget) {
			throw new Error('ChatEditor lifecycle issue: no editor widget');
		}

		if (chatSessionType !== localChatSessionType) {
			try {
				await raceCancellationError(this.chatSessionsService.canResolveChatSession(input.resource.scheme), token);
				const contributions = this.chatSessionsService.getAllChatSessionContributions();
				const contribution = contributions.find(c => c.type === chatSessionType);
				if (contribution) {
					this.widget.lockToCodingAgent(contribution.name, contribution.displayName, contribution.type);
					isContributedChatSession = true;
				} else {
					this.widget.unlockFromCodingAgent();
				}
			} catch (error) {
				this.hideLoadingInChatWidget();
				throw error;
			}
		} else {
			this.widget.unlockFromCodingAgent();
		}

		try {
			const editorModel = await raceCancellationError(input.resolve(), token);

			if (!editorModel) {
				throw new Error(`Failed to get model for chat editor. resource: ${input.sessionResource}`);
			}

			// Hide loading state before updating model
			if (chatSessionType !== localChatSessionType) {
				this.hideLoadingInChatWidget();
			}

			if (options?.modelInputState) {
				editorModel.model.inputModel.setState(options.modelInputState);
			}

			this.updateModel(editorModel.model);

			const viewState = this.loadEditorViewState(input, context);
			if (viewState) {
				this._widget.scrollTop = viewState.scrollTop;
			}

			if (isContributedChatSession && options?.title?.preferred && input.sessionResource) {
				this.chatService.setChatSessionTitle(input.sessionResource, options.title.preferred);
			}
		} catch (error) {
			this.hideLoadingInChatWidget();
			throw error;
		}
	}

	private updateModel(model: IChatModel): void {
		this.widget.setModel(model);
	}

	protected computeEditorViewState(_resource: URI): IChatEditorViewState | undefined {
		if (!this._widget) {
			return undefined;
		}
		return { scrollTop: this._widget.scrollTop };
	}

	protected tracksEditorViewState(input: EditorInput): boolean {
		return input instanceof ChatEditorInput;
	}

	protected toEditorViewStateResource(input: EditorInput): URI | undefined {
		return (input as ChatEditorInput).sessionResource;
	}

	override layout(dimension: dom.Dimension, position?: dom.IDomPosition | undefined): void {
		this.dimension = dimension;
		if (this.widget) {
			const wrapperWidth = Math.min(450, dimension.width);
			const headerHeight = 60; // rough height to account for header + spacing
			this.widget.layout(dimension.height - headerHeight, wrapperWidth - 32); // -32 for left/right padding
		}
	}
}
