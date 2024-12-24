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
