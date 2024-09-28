import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

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

import { Panel } from '@lumino/widgets';

import { ChatSidebar, RunChatCompletionType } from './chat-sidebar';
import { GitHubCopilot } from './github-copilot';

namespace CommandIDs {
  export const explainThis = 'notebook-intelligence:explain-this';
  export const fixThis = 'notebook-intelligence:fix-this';
}

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
        'python'
      ).then(response => {
        console.log(`INLINE COMPLETIONS RESPONSE\n${response}`);
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
  requires: [ICompletionProviderManager],
  optional: [ISettingRegistry],
  activate: (app: JupyterFrontEnd, completionManager: ICompletionProviderManager, settingRegistry: ISettingRegistry | null) => {
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
    const sidebar = new ChatSidebar();
    panel.addWidget(sidebar);
    app.shell.add(panel, 'left', { rank: 100 });
    app.shell.activateById(panel.id);

    app.commands.addCommand(CommandIDs.explainThis, {
      execute: (args) => {
        if (!(app.shell.currentWidget instanceof NotebookPanel)) {
          return;
        }

        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        const content = activeCell?.model.sharedModel.source;
        sidebar.runPrompt({
          type: RunChatCompletionType.ExplainThis,
          content: `Active file is main.py. Can you explain this code:\n${content}`
        });

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
        const content = activeCell?.model.sharedModel.source;

        sidebar.runPrompt({
          type: RunChatCompletionType.FixThis,
          content: `Active file is a Jupyter notebook named main.ipynb. Can you fix this code:\n${content}`
        });
      }
    });

    GitHubCopilot.initialize();
  }
};

export default plugin;
