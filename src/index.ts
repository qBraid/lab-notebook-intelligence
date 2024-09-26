import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

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

import { requestAPI } from './handler';
import { ChatSidebar } from './chat-sidebar';

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

      requestAPI<any>('inline-completions', {
        method: 'POST',
        body: JSON.stringify({
          prefix: preContent + preCursor,
          suffix: postCursor + postContent,
          language: 'python'
        })}
      )
      .then(data => {
        console.log(`INLINE COMPLETIONS RESPONSE\n${data}`);
        items.push({
          insertText: data.data
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

    let ghLoginRequested = false;
    let ghAuthenticated = false;

    const loginToGitHub = () => {
      requestAPI<any>('gh-login', {method: 'POST'})
      .then(data => {
        console.log(`Login to GitHub Copilot using ${data.verification_uri} and device code ${data.user_code}`);
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };

    const getGitHubLoginStatus = () => {
      requestAPI<any>('gh-login-status')
      .then(data => {
        ghAuthenticated = data.logged_in;
        if (!ghAuthenticated && !ghLoginRequested) {
          loginToGitHub();
          ghLoginRequested = true;
        }
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };

    setInterval(() => {
      getGitHubLoginStatus();
    }, 5000);

    getGitHubLoginStatus();

    // const testChat = () => {
    //   requestAPI<any>('chat', { method: 'POST', body: JSON.stringify({"prompt": "How can convert json to dictionary?"})})
    //   .then(data => {
    //     console.log(`CHAT RESPONSE`, data);
    //   })
    //   .catch(reason => {
    //     console.error(
    //       `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
    //     );
    //   });
    // };

    // const testInlineCompletions = () => {
    //   requestAPI<any>('inline-completions', {
    //     method: 'POST',
    //     body: JSON.stringify({
    //       prefix: 'def print_hello_world():\n',
    //       suffix: '',
    //       language: 'python'
    //     })}
    //   )
    //   .then(data => {
    //     console.log(`INLINE COMPLETIONS RESPONSE\n${data}`);
    //   })
    //   .catch(reason => {
    //     console.error(
    //       `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
    //     );
    //   });
    // };


    // setTimeout(() => {
    //   if (ghAuthenticated) {
    //     testChat();
    //     testInlineCompletions();
    //   }
    // }, 30000);

    const panel = new Panel();
    panel.id = 'notebook-intelligence-tab';
    panel.addWidget(new ChatSidebar());
    app.shell.add(panel, 'left', { rank: 100 });
    app.shell.activateById(panel.id);
  }
};

export default plugin;
