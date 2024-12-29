// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { dracula } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { VscNewFile, VscInsert, VscCopy } from "react-icons/vsc";
import { JupyterFrontEnd } from '@jupyterlab/application';

type MarkdownRendererProps = {
  children: string;
  getApp: () => JupyterFrontEnd;
};

export function MarkdownRenderer({ children: markdown, getApp }: MarkdownRendererProps) {
  const app = getApp();

  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, getApp, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const codeString = String(children).replace(/\n$/, '');

          const handleCopyClick = () => {
            navigator.clipboard.writeText(codeString);
          };
        
          const handleInsertAtCursorClick = () => {
            app.commands.execute('notebook-intelligence:insert-at-cursor', { code: codeString });
          };
        
          const handleCreateNewFileClick = () => {
            app.commands.execute('notebook-intelligence:create-new-file', { code: codeString });
          };

          return !inline && match ? (
            <div>
              <div className="code-block-header">
                <div className="code-block-header-language">
                  <span>{match[1]}</span>
                </div>
                <div className="code-block-header-button" onClick={() => handleCopyClick()}>
                  <VscCopy size={16} title='Copy to clipboard' />
                  <span>Copy</span>
                </div>
                <div className="code-block-header-button" onClick={() => handleInsertAtCursorClick()}>
                  <VscInsert size={16} title='Insert at cursor' />
                </div>
                <div className="code-block-header-button" onClick={() => handleCreateNewFileClick()}>
                  <VscNewFile size={16} title='New file' />
                </div>
              </div>
              <SyntaxHighlighter style={dracula} PreTag="div" language={match[1]} {...props}>
                {codeString}
              </SyntaxHighlighter>
            </div>
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
      }}
    >
      {markdown}
    </Markdown>
  );
}
