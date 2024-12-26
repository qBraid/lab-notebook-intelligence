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
    ChatUserInput = 'chat-user-input'
}

export enum ResponseStreamDataType {
    LLMRaw = 'llm-raw',
    Markdown = 'markdown',
    HTML = 'html',
    Button = 'button',
    Anchor = 'anchor',
    Progress = 'progress',
    Confirmation = 'confirmation'
}
