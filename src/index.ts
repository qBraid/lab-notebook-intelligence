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
import { ISharedNotebook} from '@jupyter/ydoc';

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
import {
  FileEditorWidget
} from '@jupyterlab/fileeditor';

import { IDefaultFileBrowser } from '@jupyterlab/filebrowser';

import { ContentsManager, KernelSpecManager } from '@jupyterlab/services';

import { LabIcon } from '@jupyterlab/ui-components';

import { Panel } from '@lumino/widgets';

import { ChatSidebar, RunChatCompletionType } from './chat-sidebar';
import { GitHubCopilot } from './github-copilot';
import { IActiveDocumentInfo } from './tokens';
import sparklesSvgstr from '../style/icons/sparkles.svg';

namespace CommandIDs {
  export const chatuserInput = 'notebook-intelligence:chat_user_input';
  export const insertAtCursor = 'notebook-intelligence:insert-at-cursor';
  export const createNewFile = 'notebook-intelligence:create-new-file';
  export const createNewNotebookFromPython = 'notebook-intelligence:create-new-notebook-from-py';
  export const addCodeCellToNotebook = 'notebook-intelligence:add-code-cell-to-notebook';
  export const addMarkdownCellToNotebook = 'notebook-intelligence:add-markdown-cell-to-notebook';
  export const explainThis = 'notebook-intelligence:explain-this';
  export const fixThis = 'notebook-intelligence:fix-this';
}

const emptyNotebookContent = {
  "cells": [],
  "metadata": {},
  "nbformat": 4,
  "nbformat_minor": 5
};

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
  requires: [ICompletionProviderManager, IDocumentManager, IDefaultFileBrowser],
  optional: [ISettingRegistry],
  activate: (app: JupyterFrontEnd, completionManager: ICompletionProviderManager, docManager: IDocumentManager, defaultBrowser: IDefaultFileBrowser, settingRegistry: ISettingRegistry | null) => {
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
      getApp():  JupyterFrontEnd {
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

    app.commands.addCommand(CommandIDs.insertAtCursor, {
      execute: (args) => {
        const currentWidget = app.shell.currentWidget;
        if (currentWidget instanceof NotebookPanel) {
          let activeCellIndex = currentWidget.content.activeCellIndex;
          activeCellIndex = activeCellIndex === -1 ? currentWidget.content.widgets.length : activeCellIndex;

          currentWidget.model?.sharedModel.insertCell(activeCellIndex, {
            cell_type: 'code',
            metadata: { trusted: true },
            source: args.code as string
          });
        } else if (currentWidget instanceof FileEditorWidget)  {
          const editor = currentWidget.content.editor;
          const cursor = editor.getCursorPosition();
          editor.setCursorPosition(cursor);
          editor.replaceSelection?.(args.code as string);
        } else {
          app.commands.execute('apputils:notify', {
            "message": 'Open a notebook or file to insert the code at cursor',
            "type": 'error',
            "options": { "autoClose": true }
          });
        }
      }
    });

    app.commands.addCommand(CommandIDs.createNewFile, {
      execute: async (args) => {
        const contents = new ContentsManager();
        const newPyFile = await contents.newUntitled({ext: '.py', path: defaultBrowser?.model.path});
        contents.save(newPyFile.path, { content: args.code, format: 'text', type: 'file' });
        docManager.openOrReveal(newPyFile.path);
      }
    });

    app.commands.addCommand(CommandIDs.createNewNotebookFromPython, {
      execute: async (args) => {
        let pythonKernelSpec = null;
        const contents = new ContentsManager();
        const kernels = new KernelSpecManager();
        await kernels.ready;
        const kernelspecs = kernels.specs?.kernelspecs;
        if (kernelspecs) {
          for (const key in kernelspecs) {
            const kernelspec = kernelspecs[key];
            if (kernelspec?.language === 'python') {
              pythonKernelSpec = kernelspec;
              break;
            }
          }
        }

        const newPyFile = await contents.newUntitled({ext: '.ipynb', path: defaultBrowser?.model.path});
        const nbFileContent = structuredClone(emptyNotebookContent);
        if (pythonKernelSpec) {
          nbFileContent.metadata = {
              "kernelspec": {
              "language": "python",
              "name": pythonKernelSpec.name,
            }
          };
        }

        if (args.code) {
          // @ts-ignore
          nbFileContent.cells.push({
            cell_type: 'code',
            metadata: { trusted: true },
            source: [args.code as string],
            outputs: []
          });
        }

        contents.save(newPyFile.path, { content: nbFileContent, format: 'json', type: 'notebook' });
        docManager.openOrReveal(newPyFile.path);

        return newPyFile;
      }
    });

    const isNewEmptyNotebook = (model: ISharedNotebook) => {
      return model.cells.length === 1 && model.cells[0].cell_type === 'code' && model.cells[0].source === '';
    };

    const addCellToNotebook = (filePath: string, cellType: 'code' | 'markdown', source: string): boolean => {
      const currentWidget = app.shell.currentWidget;
      const notebookOpen = currentWidget instanceof NotebookPanel && currentWidget.sessionContext.path === filePath &&
        currentWidget.model;
      if (!notebookOpen) {
        app.commands.execute('apputils:notify', {
          "message": `Failed to access the notebook: ${filePath}`,
          "type": 'error',
          "options": { "autoClose": true }
        });
        return false;
      }
      
      const model = currentWidget.model.sharedModel;

      const newCellIndex = isNewEmptyNotebook(model) ?
          0 : model.cells.length - 1;
        model.insertCell(newCellIndex, {
          cell_type: cellType,
          metadata: { trusted: true },
          source
        });

        return true;
    };

    app.commands.addCommand(CommandIDs.addCodeCellToNotebook, {
      execute: (args) => {
        return addCellToNotebook(args.path as string, 'code', args.code as string);
      }
    });

    app.commands.addCommand(CommandIDs.addMarkdownCellToNotebook, {
      execute: (args) => {
        return addCellToNotebook(args.path as string, 'markdown', args.markdown as string);
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
