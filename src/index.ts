// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  JupyterLab
} from '@jupyterlab/application';

import {
  IDocumentManager
} from '@jupyterlab/docmanager';

import { CodeCell } from '@jupyterlab/cells';

import { ISettingRegistry } from '@jupyterlab/settingregistry';

import {
  CompletionHandler,
  ICompletionProviderManager,
  IInlineCompletionContext,
  IInlineCompletionItem,
  IInlineCompletionList,
  IInlineCompletionProvider
} from '@jupyterlab/completer';

import { NotebookPanel } from '@jupyterlab/notebook';

import { LabIcon } from '@jupyterlab/ui-components';

import { Panel } from '@lumino/widgets';

import { ChatSidebar, RunChatCompletionType } from './chat-sidebar';
import { GitHubCopilot } from './github-copilot';
import { IActiveDocumentInfo } from './tokens';
import sparklesSvgstr from '../style/icons/sparkles.svg';

namespace CommandIDs {
  export const chatuserInput = 'notebook-intelligence:chat_user_input';
  export const explainThis = 'notebook-intelligence:explain-this';
  export const fixThis = 'notebook-intelligence:fix-this';
}

const activeDocumentInfo: IActiveDocumentInfo = {
  language: 'python',
  filename: 'Untitled.ipynb'
};

class GitHubInlineCompletionProvider implements IInlineCompletionProvider<IInlineCompletionItem> {
  fetch(
    request: CompletionHandler.IRequest,
    context: IInlineCompletionContext
  ): Promise<IInlineCompletionList<IInlineCompletionItem>> {
    let preContent = '';
    let postContent = '';
    const preCursor = request.text.substring(0, request.offset);
    const postCursor = request.text.substring(request.offset);

    if (context.widget instanceof NotebookPanel) {
      const activeCell = context.widget.content.activeCell;
      let activeCellReached = false;

      for (const cell of context.widget.content.widgets) {
        const cellModel = cell.model.sharedModel;
        if (cell === activeCell) {
          activeCellReached = true;
        } else if (!activeCellReached) {
          if (cellModel.cell_type === 'code') {
            preContent += cellModel.source + '\n';
          }
        } else {
          if (cellModel.cell_type === 'code') {
            postContent += cellModel.source + '\n';
          }
        }
      }
    }

    return new Promise((resolve, reject) => {
      const items: IInlineCompletionItem[] = [];

      GitHubCopilot.inlineCompletionsRequest(
        preContent + preCursor,
        postCursor + postContent,
        activeDocumentInfo.language,
        activeDocumentInfo.filename
      ).then(response => {
        items.push({
          insertText: response.data
        });

        resolve({items});
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    });
  }

  get name(): string {
    return 'Notebook Intelligence';
  }

  get identifier(): string {
    return '@mbektas/jupyter-notebook-intelligence';
  }
}

/**
 * Initialization data for the @mbektas/jupyter-notebook-intelligence extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: '@mbektas/jupyter-notebook-intelligence:plugin',
  description: 'Jupyter Notebook Intelligence extension',
  autoStart: true,
  requires: [ICompletionProviderManager, IDocumentManager],
  optional: [ISettingRegistry],
  activate: (app: JupyterFrontEnd, completionManager: ICompletionProviderManager, docManager: IDocumentManager, settingRegistry: ISettingRegistry | null) => {
    console.log('JupyterLab extension @mbektas/jupyter-notebook-intelligence is activated!');

    completionManager.registerInlineProvider(new GitHubInlineCompletionProvider());

    if (settingRegistry) {
      settingRegistry
        .load(plugin.id)
        .then(settings => {
          console.log('@mbektas/jupyter-notebook-intelligence settings loaded:', settings.composite);
        })
        .catch(reason => {
          console.error('Failed to load settings for @mbektas/jupyter-notebook-intelligence.', reason);
        });
    }

    const panel = new Panel();
    panel.id = 'notebook-intelligence-tab';
    panel.title.caption = 'Copilot Chat';
    const sidebarIcon = new LabIcon({ name: 'ui-components:palette', svgstr: sparklesSvgstr });
    panel.title.icon = sidebarIcon;
    const sidebar = new ChatSidebar({
      getActiveDocumentInfo: () : IActiveDocumentInfo => {
        return activeDocumentInfo;
      },
      openFile: (path: string) => {
        docManager.openOrReveal(path);
      },
      getApp():  JupyterFrontEnd<JupyterFrontEnd.IShell, "desktop" | "mobile"> {
        return app;
      },
    });
    panel.addWidget(sidebar);
    app.shell.add(panel, 'left', { rank: 1000 });
    app.shell.activateById(panel.id);

    app.commands.addCommand(CommandIDs.chatuserInput, {
      execute: (args) => {
        // @ts-ignore
        GitHubCopilot.sendChatUserInput(args.id, args.data);
      }
    });

    app.commands.addCommand(CommandIDs.explainThis, {
      execute: (args) => {
        if (!(app.shell.currentWidget instanceof NotebookPanel)) {
          return;
        }

        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        const content = activeCell?.model.sharedModel.source || '';
        document.dispatchEvent(new CustomEvent("copilotSidebar:runPrompt", {
          detail: {
            type: RunChatCompletionType.ExplainThis,
            content,
            language: activeDocumentInfo.language,
            filename: activeDocumentInfo.filename,
          }
        }));

        app.commands.execute('tabsmenu:activate-by-id', {"id": panel.id});
      }
    });

    app.commands.addCommand(CommandIDs.fixThis, {
      execute: (args) => {
        if (!(app.shell.currentWidget instanceof NotebookPanel)) {
          return;
        }

        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell as CodeCell;
        const content = activeCell?.model.sharedModel.source || "";

        document.dispatchEvent(new CustomEvent("copilotSidebar:runPrompt", {
          detail: {
            type: RunChatCompletionType.FixThis,
            content,
            language: activeDocumentInfo.language,
            filename: activeDocumentInfo.filename,
          }
        }));
      }
    });

    const jlabApp = (app as JupyterLab);
    activeDocumentInfo.serverRoot = jlabApp.paths.directories.serverRoot;
    activeDocumentInfo.parentDirectory = activeDocumentInfo.serverRoot + '/';

    app.shell.currentChanged?.connect((_sender, args) => {
      if (args.newValue instanceof NotebookPanel) {
        const np = args.newValue as NotebookPanel;
        activeDocumentInfo.filename = np.sessionContext.name;
        activeDocumentInfo.language = np.model?.sharedModel?.metadata?.kernelspec?.language as string || 'python';
        const lastSlashIndex = np.sessionContext.path.lastIndexOf('/');
        const nbFolder = lastSlashIndex === -1 ? '' : np.sessionContext.path.substring(0, lastSlashIndex);
        activeDocumentInfo.parentDirectory = activeDocumentInfo.serverRoot + '/' + nbFolder;
      }
    });

    GitHubCopilot.initialize();
  }
};

export default plugin;
