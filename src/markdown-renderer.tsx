// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import {
  oneLight,
  oneDark
} from 'react-syntax-highlighter/dist/cjs/styles/prism';
import {
  VscNewFile,
  VscInsert,
  VscCopy,
  VscNotebook,
  VscAdd
} from 'react-icons/vsc';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { isDarkTheme } from './utils';
import { IActiveDocumentInfo } from './tokens';

type MarkdownRendererProps = {
  children: string;
  getApp: () => JupyterFrontEnd;
  getActiveDocumentInfo(): IActiveDocumentInfo;
};

export function MarkdownRenderer({
  children: markdown,
  getApp,
  getActiveDocumentInfo
}: MarkdownRendererProps) {
  const app = getApp();
  const activeDocumentInfo = getActiveDocumentInfo();
  const isNotebook = activeDocumentInfo.filename.endsWith('.ipynb');

  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, getApp, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const codeString = String(children).replace(/\n$/, '');
          const language = match ? match[1] : 'text';

          const handleCopyClick = () => {
            navigator.clipboard.writeText(codeString);
          };

          const handleInsertAtCursorClick = () => {
            app.commands.execute('lab-notebook-intelligence:insert-at-cursor', {
              language,
              code: codeString
            });
          };

          const handleAddCodeAsNewCell = () => {
            app.commands.execute(
              'lab-notebook-intelligence:add-code-as-new-cell',
              {
                language,
                code: codeString
              }
            );
          };

          const handleCreateNewFileClick = () => {
            app.commands.execute('lab-notebook-intelligence:create-new-file', {
              language,
              code: codeString
            });
          };

          const handleCreateNewNotebookClick = () => {
            app.commands.execute(
              'lab-notebook-intelligence:create-new-notebook-from-py',
              { language, code: codeString }
            );
          };

          return !inline && match ? (
            <div>
              <div className="code-block-header">
                <div className="code-block-header-language">
                  <span>{language}</span>
                </div>
                <div
                  className="code-block-header-button"
                  onClick={() => handleCopyClick()}
                >
                  <VscCopy size={16} title="Copy to clipboard" />
                  <span>Copy</span>
                </div>
                <div
                  className="code-block-header-button"
                  onClick={() => handleInsertAtCursorClick()}
                >
                  <VscInsert size={16} title="Insert at cursor" />
                </div>
                {isNotebook && (
                  <div
                    className="code-block-header-button"
                    onClick={() => handleAddCodeAsNewCell()}
                  >
                    <VscAdd size={16} title="Add as new cell" />
                  </div>
                )}
                <div
                  className="code-block-header-button"
                  onClick={() => handleCreateNewFileClick()}
                >
                  <VscNewFile size={16} title="New file" />
                </div>
                {language === 'python' && (
                  <div
                    className="code-block-header-button"
                    onClick={() => handleCreateNewNotebookClick()}
                  >
                    <VscNotebook size={16} title="New notebook" />
                  </div>
                )}
              </div>
              <SyntaxHighlighter
                style={isDarkTheme() ? oneDark : oneLight}
                PreTag="div"
                language={language}
                {...props}
              >
                {codeString}
              </SyntaxHighlighter>
            </div>
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          );
        }
      }}
    >
      {markdown}
    </Markdown>
  );
}
