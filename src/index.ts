// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  JupyterLab
} from '@jupyterlab/application';

import { IDocumentManager } from '@jupyterlab/docmanager';

import { Dialog } from '@jupyterlab/apputils';

import { URLExt } from '@jupyterlab/coreutils';

import { CodeCell } from '@jupyterlab/cells';
import { ISharedNotebook } from '@jupyter/ydoc';

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
import { FileEditorWidget } from '@jupyterlab/fileeditor';

import { IDefaultFileBrowser } from '@jupyterlab/filebrowser';

import { ContentsManager, KernelSpecManager } from '@jupyterlab/services';

import { LabIcon } from '@jupyterlab/ui-components';

import { Menu, Panel, Widget } from '@lumino/widgets';
import { CommandRegistry } from '@lumino/commands';
import { IStatusBar } from '@jupyterlab/statusbar';

import {
  ChatSidebar,
  GitHubCopilotLoginDialogBody,
  GitHubCopilotStatusBarItem,
  InlinePromptWidget,
  RunChatCompletionType
} from './chat-sidebar';
import { GitHubCopilot } from './github-copilot';
import { IActiveDocumentInfo } from './tokens';
import sparklesSvgstr from '../style/icons/sparkles.svg';
import {
  extractCodeFromMarkdown,
  removeAnsiChars,
  waitForDuration
} from './utils';

namespace CommandIDs {
  export const chatuserInput = 'notebook-intelligence:chat-user-input';
  export const insertAtCursor = 'notebook-intelligence:insert-at-cursor';
  export const createNewFile = 'notebook-intelligence:create-new-file';
  export const createNewNotebookFromPython =
    'notebook-intelligence:create-new-notebook-from-py';
  export const addCodeCellToNotebook =
    'notebook-intelligence:add-code-cell-to-notebook';
  export const addMarkdownCellToNotebook =
    'notebook-intelligence:add-markdown-cell-to-notebook';
  export const editorGenerateCode =
    'notebook-intelligence:editor-generate-code';
  export const editorExplainThisCode =
    'notebook-intelligence:editor-explain-this-code';
  export const editorFixThisCode = 'notebook-intelligence:editor-fix-this-code';
  export const editorExplainThisOutput =
    'notebook-intelligence:editor-explain-this-output';
  export const editorTroubleshootThisOutput =
    'notebook-intelligence:editor-troubleshoot-this-output';
  export const openGitHubCopilotLoginDialog =
    'notebook-intelligence:open-github-copilot-login-dialog';
}

const emptyNotebookContent = {
  cells: [],
  metadata: {},
  nbformat: 4,
  nbformat_minor: 5
};

const activeDocumentInfo: IActiveDocumentInfo = {
  language: 'python',
  filename: 'Untitled.ipynb'
};

class GitHubInlineCompletionProvider
  implements IInlineCompletionProvider<IInlineCompletionItem>
{
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
      )
        .then(response => {
          items.push({
            insertText: response.data
          });

          resolve({ items });
        })
        .catch(reason => {
          console.error(
            `The notebook_intelligence server extension appears to be missing.\n${reason}`
          );
        });
    });
  }

  get name(): string {
    return 'Notebook Intelligence';
  }

  get identifier(): string {
    return '@mbektas/notebook-intelligence';
  }
}

/**
 * Initialization data for the @mbektas/notebook-intelligence extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: '@mbektas/notebook-intelligence:plugin',
  description: 'Notebook Intelligence',
  autoStart: true,
  requires: [ICompletionProviderManager, IDocumentManager, IDefaultFileBrowser],
  optional: [ISettingRegistry, IStatusBar],
  activate: (
    app: JupyterFrontEnd,
    completionManager: ICompletionProviderManager,
    docManager: IDocumentManager,
    defaultBrowser: IDefaultFileBrowser,
    settingRegistry: ISettingRegistry | null,
    statusBar: IStatusBar | null
  ) => {
    console.log(
      'JupyterLab extension @mbektas/notebook-intelligence is activated!'
    );

    new LabIcon({
      name: 'notebook-intelligence:sparkles-icon',
      svgstr: sparklesSvgstr
    });

    completionManager.registerInlineProvider(
      new GitHubInlineCompletionProvider()
    );

    if (settingRegistry) {
      settingRegistry
        .load(plugin.id)
        .then(settings => {
          console.log(
            '@mbektas/notebook-intelligence settings loaded:',
            settings.composite
          );
        })
        .catch(reason => {
          console.error(
            'Failed to load settings for @mbektas/notebook-intelligence.',
            reason
          );
        });
    }

    const waitForFileToBeActive = async (
      filePath: string
    ): Promise<boolean> => {
      const isNotebook = filePath.endsWith('.ipynb');

      return new Promise<boolean>((resolve, reject) => {
        const checkIfActive = () => {
          const activeFilePath = URLExt.join(
            activeDocumentInfo.parentDirectory || '',
            activeDocumentInfo.filename
          );
          const filePathToCheck = URLExt.join(
            activeDocumentInfo.serverRoot || '',
            filePath
          );
          const currentWidget = app.shell.currentWidget;
          if (
            activeFilePath === filePathToCheck &&
            ((isNotebook &&
              currentWidget instanceof NotebookPanel &&
              currentWidget.content.activeCell &&
              currentWidget.content.activeCell.node.contains(
                document.activeElement
              )) ||
              (!isNotebook &&
                currentWidget instanceof FileEditorWidget &&
                currentWidget.content.editor.hasFocus()))
          ) {
            resolve(true);
          } else {
            setTimeout(checkIfActive, 200);
          }
        };
        checkIfActive();

        waitForDuration(10000).then(() => {
          resolve(false);
        });
      });
    };

    const panel = new Panel();
    panel.id = 'notebook-intelligence-tab';
    panel.title.caption = 'Copilot Chat';
    const sidebarIcon = new LabIcon({
      name: 'ui-components:palette',
      svgstr: sparklesSvgstr
    });
    panel.title.icon = sidebarIcon;
    const sidebar = new ChatSidebar({
      getActiveDocumentInfo: (): IActiveDocumentInfo => {
        return activeDocumentInfo;
      },
      openFile: (path: string) => {
        docManager.openOrReveal(path);
      },
      getApp(): JupyterFrontEnd {
        return app;
      }
    });
    panel.addWidget(sidebar);
    app.shell.add(panel, 'left', { rank: 1000 });
    app.shell.activateById(panel.id);

    app.commands.addCommand(CommandIDs.chatuserInput, {
      execute: args => {
        GitHubCopilot.sendChatUserInput(args.id as string, args.data);
      }
    });

    app.commands.addCommand(CommandIDs.insertAtCursor, {
      execute: args => {
        const currentWidget = app.shell.currentWidget;
        if (currentWidget instanceof NotebookPanel) {
          let activeCellIndex = currentWidget.content.activeCellIndex;
          activeCellIndex =
            activeCellIndex === -1
              ? currentWidget.content.widgets.length
              : activeCellIndex;

          currentWidget.model?.sharedModel.insertCell(activeCellIndex, {
            cell_type: 'code',
            metadata: { trusted: true },
            source: args.code as string
          });
        } else if (currentWidget instanceof FileEditorWidget) {
          const editor = currentWidget.content.editor;
          const cursor = editor.getCursorPosition();
          editor.setCursorPosition(cursor);
          editor.replaceSelection?.(args.code as string);
        } else {
          app.commands.execute('apputils:notify', {
            message: 'Open a notebook or file to insert the code at cursor',
            type: 'error',
            options: { autoClose: true }
          });
        }
      }
    });

    app.commands.addCommand(CommandIDs.createNewFile, {
      execute: async args => {
        const contents = new ContentsManager();
        const newPyFile = await contents.newUntitled({
          ext: '.py',
          path: defaultBrowser?.model.path
        });
        contents.save(newPyFile.path, {
          content: extractCodeFromMarkdown(args.code as string),
          format: 'text',
          type: 'file'
        });
        docManager.openOrReveal(newPyFile.path);

        await waitForFileToBeActive(newPyFile.path);

        return newPyFile;
      }
    });

    app.commands.addCommand(CommandIDs.createNewNotebookFromPython, {
      execute: async args => {
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

        const newNBFile = await contents.newUntitled({
          ext: '.ipynb',
          path: defaultBrowser?.model.path
        });
        const nbFileContent = structuredClone(emptyNotebookContent);
        if (pythonKernelSpec) {
          nbFileContent.metadata = {
            kernelspec: {
              language: 'python',
              name: pythonKernelSpec.name
            }
          };
        }

        if (args.code) {
          // @ts-expect-error - code is valid
          nbFileContent.cells.push({
            cell_type: 'code',
            metadata: { trusted: true },
            source: [args.code as string],
            outputs: []
          });
        }

        contents.save(newNBFile.path, {
          content: nbFileContent,
          format: 'json',
          type: 'notebook'
        });
        docManager.openOrReveal(newNBFile.path);

        await waitForFileToBeActive(newNBFile.path);

        return newNBFile;
      }
    });

    const isNewEmptyNotebook = (model: ISharedNotebook) => {
      return (
        model.cells.length === 1 &&
        model.cells[0].cell_type === 'code' &&
        model.cells[0].source === ''
      );
    };

    const isActiveCellCodeCell = (): boolean => {
      if (!(app.shell.currentWidget instanceof NotebookPanel)) {
        return false;
      }
      const np = app.shell.currentWidget as NotebookPanel;
      const activeCell = np.content.activeCell;
      return activeCell instanceof CodeCell;
    };

    const addCellToNotebook = (
      filePath: string,
      cellType: 'code' | 'markdown',
      source: string
    ): boolean => {
      const currentWidget = app.shell.currentWidget;
      const notebookOpen =
        currentWidget instanceof NotebookPanel &&
        currentWidget.sessionContext.path === filePath &&
        currentWidget.model;
      if (!notebookOpen) {
        app.commands.execute('apputils:notify', {
          message: `Failed to access the notebook: ${filePath}`,
          type: 'error',
          options: { autoClose: true }
        });
        return false;
      }

      const model = currentWidget.model.sharedModel;

      const newCellIndex = isNewEmptyNotebook(model)
        ? 0
        : model.cells.length - 1;
      model.insertCell(newCellIndex, {
        cell_type: cellType,
        metadata: { trusted: true },
        source
      });

      return true;
    };

    app.commands.addCommand(CommandIDs.addCodeCellToNotebook, {
      execute: args => {
        return addCellToNotebook(
          args.path as string,
          'code',
          args.code as string
        );
      }
    });

    app.commands.addCommand(CommandIDs.addMarkdownCellToNotebook, {
      execute: args => {
        return addCellToNotebook(
          args.path as string,
          'markdown',
          args.markdown as string
        );
      }
    });

    app.commands.addCommand(CommandIDs.openGitHubCopilotLoginDialog, {
      execute: args => {
        let dialog: Dialog<unknown> | null = null;
        const dialogBody = new GitHubCopilotLoginDialogBody({
          onLoggedIn: () => dialog?.dispose()
        });
        dialog = new Dialog({
          title: 'GitHub Copilot Status',
          hasClose: true,
          body: dialogBody,
          buttons: []
        });

        dialog.launch();
      }
    });

    const getPrefixAndSuffixForActiveCell = (): {
      prefix: string;
      suffix: string;
    } => {
      let prefix = '';
      let suffix = '';
      const currentWidget = app.shell.currentWidget;
      if (
        !(
          currentWidget instanceof NotebookPanel &&
          currentWidget.content.activeCell
        )
      ) {
        return { prefix, suffix };
      }

      const activeCell = currentWidget.content.activeCell;
      let activeCellReached = false;

      for (const cell of currentWidget.content.widgets) {
        const cellModel = cell.model.sharedModel;
        if (cell === activeCell) {
          activeCellReached = true;
        } else if (!activeCellReached) {
          if (cellModel.cell_type === 'code') {
            prefix += cellModel.source + '\n';
          }
        } else {
          if (cellModel.cell_type === 'code') {
            suffix += cellModel.source + '\n';
          }
        }
      }

      return { prefix, suffix };
    };

    const generateCodeCommand: CommandRegistry.ICommandOptions = {
      execute: args => {
        const currentWidget = app.shell.currentWidget;
        if (
          !(
            currentWidget instanceof NotebookPanel &&
            currentWidget.content.activeCell
          )
        ) {
          return;
        }
        const activeCell = currentWidget.content.activeCell;
        const input = activeCell.node.querySelector('.jp-InputArea-editor');
        if (!input) {
          return;
        }
        const rect = input.getBoundingClientRect();

        const NBI_PROMPT_PREFIX = '# nbi-prompt:';
        let userPrompt = '';
        let generatedContent = '';

        let existingCode = activeCell.model.sharedModel.source.trim();
        const existingLines = existingCode.split('\n');
        if (existingLines.length > 0) {
          if (existingLines[0].startsWith(NBI_PROMPT_PREFIX)) {
            userPrompt = existingLines[0]
              .substring(NBI_PROMPT_PREFIX.length)
              .trim();
            existingCode =
              existingLines.length > 1 ? existingLines.slice(1).join('\n') : '';
          }
        }

        const removePromptComments = (source: string): string => {
          source = source.trim();
          const existingLines = source.split('\n');
          const newLines = existingLines.filter(
            line => !line.startsWith(NBI_PROMPT_PREFIX)
          );
          return newLines.join('\n');
        };

        const { prefix, suffix } = getPrefixAndSuffixForActiveCell();

        const inlinePrompt = new InlinePromptWidget(rect, {
          prompt: userPrompt,
          existingCode,
          prefix: removePromptComments(prefix),
          suffix: removePromptComments(suffix),
          onRequestSubmitted: (prompt: string) => {
            userPrompt = prompt;
            inlinePrompt.hide();
          },
          onRequestCancelled: () => {
            Widget.detach(inlinePrompt);
          },
          onContentStream: (content: string) => {
            generatedContent += content;
            activeCell.model.sharedModel.source = generatedContent;
          },
          onContentStreamEnd: () => {
            // extract out code sections from markdown
            generatedContent = `${NBI_PROMPT_PREFIX} ${userPrompt}\n${extractCodeFromMarkdown(generatedContent)}`;
            activeCell.model.sharedModel.source = generatedContent;
            generatedContent = '';
            Widget.detach(inlinePrompt);
          }
        });
        Widget.attach(inlinePrompt, document.body);
      },
      label: 'Generate code',
      isEnabled: isActiveCellCodeCell
    };
    app.commands.addCommand(CommandIDs.editorGenerateCode, generateCodeCommand);

    const copilotMenuCommands = new CommandRegistry();
    copilotMenuCommands.addCommand(
      CommandIDs.editorGenerateCode,
      generateCodeCommand
    );
    copilotMenuCommands.addCommand(CommandIDs.editorExplainThisCode, {
      execute: () => {
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        const content = activeCell?.model.sharedModel.source || '';
        document.dispatchEvent(
          new CustomEvent('copilotSidebar:runPrompt', {
            detail: {
              type: RunChatCompletionType.ExplainThis,
              content,
              language: activeDocumentInfo.language,
              filename: activeDocumentInfo.filename
            }
          })
        );

        app.commands.execute('tabsmenu:activate-by-id', { id: panel.id });
      },
      label: 'Explain code',
      isEnabled: isActiveCellCodeCell
    });
    copilotMenuCommands.addCommand(CommandIDs.editorFixThisCode, {
      execute: () => {
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        const content = activeCell?.model.sharedModel.source || '';
        document.dispatchEvent(
          new CustomEvent('copilotSidebar:runPrompt', {
            detail: {
              type: RunChatCompletionType.FixThis,
              content,
              language: activeDocumentInfo.language,
              filename: activeDocumentInfo.filename
            }
          })
        );

        app.commands.execute('tabsmenu:activate-by-id', { id: panel.id });
      },
      label: 'Fix code',
      isEnabled: isActiveCellCodeCell
    });
    copilotMenuCommands.addCommand(CommandIDs.editorExplainThisOutput, {
      execute: () => {
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        let content = '';
        const outputs = (activeCell as CodeCell).outputArea.model.toJSON();
        for (const output of outputs) {
          if (output.output_type === 'execute_result') {
            content += output.data['text/plain'] + '\n';
          } else if (output.output_type === 'stream') {
            content += output.text + '\n';
          } else if (output.output_type === 'error') {
            if (Array.isArray(output.traceback)) {
              content += output.ename + ': ' + output.evalue + '\n';
              content +=
                output.traceback
                  .map(item => removeAnsiChars(item as string))
                  .join('\n') + '\n';
            }
          }
        }
        document.dispatchEvent(
          new CustomEvent('copilotSidebar:runPrompt', {
            detail: {
              type: RunChatCompletionType.ExplainThisOutput,
              content,
              language: activeDocumentInfo.language,
              filename: activeDocumentInfo.filename
            }
          })
        );

        app.commands.execute('tabsmenu:activate-by-id', { id: panel.id });
      },
      label: 'Explain output',
      isEnabled: () => {
        if (!(app.shell.currentWidget instanceof NotebookPanel)) {
          return false;
        }
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        if (!(activeCell instanceof CodeCell)) {
          return false;
        }
        const outputs = activeCell.outputArea.model.toJSON();
        return Array.isArray(outputs) && outputs.length > 0;
      }
    });
    copilotMenuCommands.addCommand(CommandIDs.editorTroubleshootThisOutput, {
      execute: () => {
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        let content = '';
        const outputs = (activeCell as CodeCell).outputArea.model.toJSON();
        for (const output of outputs) {
          if (output.output_type === 'error') {
            if (Array.isArray(output.traceback)) {
              content += output.ename + ': ' + output.evalue + '\n';
              content +=
                output.traceback
                  .map(item => removeAnsiChars(item as string))
                  .join('\n') + '\n';
            }
          }
        }
        document.dispatchEvent(
          new CustomEvent('copilotSidebar:runPrompt', {
            detail: {
              type: RunChatCompletionType.TroubleshootThisOutput,
              content,
              language: activeDocumentInfo.language,
              filename: activeDocumentInfo.filename
            }
          })
        );

        app.commands.execute('tabsmenu:activate-by-id', { id: panel.id });
      },
      label: 'Troubleshoot errors in output',
      isEnabled: () => {
        if (!(app.shell.currentWidget instanceof NotebookPanel)) {
          return false;
        }
        const np = app.shell.currentWidget as NotebookPanel;
        const activeCell = np.content.activeCell;
        if (!(activeCell instanceof CodeCell)) {
          return false;
        }
        const outputs = activeCell.outputArea.model.toJSON();
        return (
          Array.isArray(outputs) &&
          outputs.length > 0 &&
          outputs.some(output => output.output_type === 'error')
        );
      }
    });

    const copilotContextMenu = new Menu({ commands: copilotMenuCommands });
    copilotContextMenu.id = 'notebook-intelligence:editor-context-menu';
    copilotContextMenu.title.label = 'Copilot';
    copilotContextMenu.title.icon = sidebarIcon;
    copilotContextMenu.addItem({ command: CommandIDs.editorGenerateCode });
    copilotContextMenu.addItem({ command: CommandIDs.editorExplainThisCode });
    copilotContextMenu.addItem({ command: CommandIDs.editorFixThisCode });
    copilotContextMenu.addItem({ command: CommandIDs.editorExplainThisOutput });
    copilotContextMenu.addItem({
      command: CommandIDs.editorTroubleshootThisOutput
    });

    app.contextMenu.addItem({
      type: 'submenu',
      submenu: copilotContextMenu,
      selector: '.jp-Editor',
      rank: 1
    });

    if (statusBar) {
      const githubCopilotStatusBarItem = new GitHubCopilotStatusBarItem({
        getApp: () => app
      });

      statusBar.registerStatusItem(
        'notebook-intelligence:github-copilot-status',
        {
          item: githubCopilotStatusBarItem,
          align: 'right',
          rank: 100,
          isActive: () => true
        }
      );
    }

    const jlabApp = app as JupyterLab;
    activeDocumentInfo.serverRoot = jlabApp.paths.directories.serverRoot;
    activeDocumentInfo.parentDirectory = activeDocumentInfo.serverRoot + '/';

    app.shell.currentChanged?.connect((_sender, args) => {
      if (args.newValue instanceof NotebookPanel) {
        const np = args.newValue as NotebookPanel;
        activeDocumentInfo.filename = np.sessionContext.name;
        activeDocumentInfo.language =
          (np.model?.sharedModel?.metadata?.kernelspec?.language as string) ||
          'python';
        const lastSlashIndex = np.sessionContext.path.lastIndexOf('/');
        const nbFolder =
          lastSlashIndex === -1
            ? ''
            : np.sessionContext.path.substring(0, lastSlashIndex);
        activeDocumentInfo.parentDirectory =
          activeDocumentInfo.serverRoot + '/' + nbFolder;
      } else if (args.newValue instanceof FileEditorWidget) {
        const fe = args.newValue as FileEditorWidget;
        activeDocumentInfo.filename = fe.context.path;
        activeDocumentInfo.language = 'python';
        const lastSlashIndex = fe.context.path.lastIndexOf('/');
        const nbFolder =
          lastSlashIndex === -1
            ? ''
            : fe.context.path.substring(0, lastSlashIndex);
        activeDocumentInfo.parentDirectory =
          activeDocumentInfo.serverRoot + '/' + nbFolder;
      }
    });

    GitHubCopilot.initialize();
  }
};

export default plugin;
