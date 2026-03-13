/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *  Licensed under the MIT License. See License.txt in the project root for license information.
 *--------------------------------------------------------------------------------------------*/

import { localize2 } from '../../../../nls.js';
import { Registry } from '../../../../platform/registry/common/platform.js';
import { Extensions as ViewContainerExtensions, IViewContainersRegistry, ViewContainerLocation } from '../../../common/views.js';
import { ViewPaneContainer } from '../../../browser/parts/views/viewPaneContainer.js';
import { SyncDescriptor } from '../../../../platform/instantiation/common/descriptors.js';
import { agentManagerViewIcon } from './agentIcons.js';

export const AGENT_MANAGER_VIEW_CONTAINER_ID = 'workbench.view.agentManager';

Registry.as<IViewContainersRegistry>(ViewContainerExtensions.ViewContainersRegistry).registerViewContainer(
	{
		id: AGENT_MANAGER_VIEW_CONTAINER_ID,
		title: localize2('agentManager', "Agent Manager"),
		ctorDescriptor: new SyncDescriptor(ViewPaneContainer, [AGENT_MANAGER_VIEW_CONTAINER_ID, { mergeViewWithContainerWhenSingleView: true }]),
		icon: agentManagerViewIcon,
		order: 5,
		hideIfEmpty: false,
	}, ViewContainerLocation.Sidebar);
