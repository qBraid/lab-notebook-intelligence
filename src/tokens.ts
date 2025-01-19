// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

export interface IActiveDocumentInfo {
  language: string;
  filename: string;
  serverRoot?: string;
  parentDirectory?: string;
}

export interface IChatCompletionResponseEmitter {
  emit: (response: any) => void;
}

export enum RequestDataType {
  ChatRequest = 'chat-request',
  ChatUserInput = 'chat-user-input',
  ClearChatHistory = 'clear-chat-history',
  RunUICommandResponse = 'run-ui-command-response',
  GenerateCode = 'generate-code',
  CancelChatRequest = 'cancel-chat-request'
}

export enum BackendMessageType {
  StreamMessage = 'stream-message',
  StreamEnd = 'stream-end',
  RunUICommand = 'run-ui-command'
}

export enum ResponseStreamDataType {
  LLMRaw = 'llm-raw',
  Markdown = 'markdown',
  MarkdownPart = 'markdown-part',
  HTMLFrame = 'html-frame',
  Button = 'button',
  Anchor = 'anchor',
  Progress = 'progress',
  Confirmation = 'confirmation'
}
