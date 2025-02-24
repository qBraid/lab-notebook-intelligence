// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { ServerConnection } from '@jupyterlab/services';
import { requestAPI } from './handler';
import { URLExt } from '@jupyterlab/coreutils';
import { UUID } from '@lumino/coreutils';
import { Signal } from '@lumino/signaling';
import {
  GITHUB_COPILOT_MODEL_ID_PREFIX,
  IChatCompletionResponseEmitter,
  IContextItem,
  RequestDataType
} from './tokens';

const LOGIN_STATUS_UPDATE_INTERVAL = 2000;

export enum GitHubCopilotLoginStatus {
  NotLoggedIn = 'NOT_LOGGED_IN',
  ActivatingDevice = 'ACTIVATING_DEVICE',
  LoggingIn = 'LOGGING_IN',
  LoggedIn = 'LOGGED_IN'
}

export interface IDeviceVerificationInfo {
  verificationURI: string;
  userCode: string;
}

export class NBIConfig {
  get chatModels(): [any] {
    return this.capabilities.chat_models;
  }

  get inlineCompletionModels(): [any] {
    return this.capabilities.inline_completion_models;
  }

  get chatModel(): string {
    return this.capabilities.chat_model;
  }

  get inlineCompletionModel(): string {
    return this.capabilities.inline_completion_model;
  }

  get openAICompatibleChatModelId(): string {
    return this.capabilities.openai_compatible_chat_model_id;
  }

  get openAICompatibleChatModelBaseUrl(): string {
    return this.capabilities.openai_compatible_chat_model_base_url;
  }

  get openAICompatibleChatModelApiKey(): string {
    return this.capabilities.openai_compatible_chat_model_api_key;
  }

  get openAICompatibleInlineCompletionModelId(): string {
    return this.capabilities.openai_compatible_inline_completion_model_id;
  }

  get openAICompatibleInlineCompletionModelBaseUrl(): string {
    return this.capabilities.openai_compatible_inline_completion_model_base_url;
  }

  get openAICompatibleInlineCompletionModelApiKey(): string {
    return this.capabilities.openai_compatible_inline_completion_model_api_key;
  }

  get usingGitHubCopilotModel(): boolean {
    const prefix = `${GITHUB_COPILOT_MODEL_ID_PREFIX}::`;
    return (
      this.chatModel.startsWith(prefix) ||
      this.inlineCompletionModel.startsWith(prefix)
    );
  }

  capabilities: any = {};
}

export class GitHubCopilot {
  static _loginStatus = GitHubCopilotLoginStatus.NotLoggedIn;
  static _deviceVerificationInfo: IDeviceVerificationInfo = {
    verificationURI: '',
    userCode: ''
  };
  static _webSocket: WebSocket;
  static _messageReceived = new Signal<unknown, any>(this);
  static config = new NBIConfig();

  static async initialize() {
    await this.fetchCapabilities();
    this.updateGitHubLoginStatus();

    setInterval(() => {
      this.updateGitHubLoginStatus();
    }, LOGIN_STATUS_UPDATE_INTERVAL);

    GitHubCopilot.initializeWebsocket();
  }

  static async initializeWebsocket() {
    const serverSettings = ServerConnection.makeSettings();
    const wsUrl = URLExt.join(
      serverSettings.wsUrl,
      'notebook-intelligence',
      'copilot'
    );

    this._webSocket = new WebSocket(wsUrl);
    this._webSocket.onmessage = msg => {
      this._messageReceived.emit(msg.data);
    };
  }

  static getLoginStatus(): GitHubCopilotLoginStatus {
    return this._loginStatus;
  }

  static getDeviceVerificationInfo(): IDeviceVerificationInfo {
    return this._deviceVerificationInfo;
  }

  static async loginToGitHub() {
    this._loginStatus = GitHubCopilotLoginStatus.ActivatingDevice;
    return new Promise((resolve, reject) => {
      requestAPI<any>('gh-login', { method: 'POST' })
        .then(data => {
          resolve({
            verificationURI: data.verification_uri,
            userCode: data.user_code
          });
          this.updateGitHubLoginStatus();
        })
        .catch(reason => {
          console.error(`Failed to login to GitHub Copilot.\n${reason}`);
          reject(reason);
        });
    });
  }

  static async logoutFromGitHub() {
    this._loginStatus = GitHubCopilotLoginStatus.ActivatingDevice;
    return new Promise((resolve, reject) => {
      requestAPI<any>('gh-logout', { method: 'GET' })
        .then(data => {
          this.updateGitHubLoginStatus().then(() => {
            resolve(data);
          });
        })
        .catch(reason => {
          console.error(`Failed to logout from GitHub Copilot.\n${reason}`);
          reject(reason);
        });
    });
  }

  static async updateGitHubLoginStatus() {
    return new Promise<void>((resolve, reject) => {
      requestAPI<any>('gh-login-status')
        .then(response => {
          this._loginStatus = response.status;
          this._deviceVerificationInfo.verificationURI =
            response.verification_uri || '';
          this._deviceVerificationInfo.userCode = response.user_code || '';
          resolve();
        })
        .catch(reason => {
          console.error(
            `Failed to fetch GitHub Copilot login status.\n${reason}`
          );
          reject(reason);
        });
    });
  }

  static async fetchCapabilities(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      requestAPI<any>('capabilities', { method: 'GET' })
        .then(data => {
          this.config.capabilities = structuredClone(data);
          resolve();
        })
        .catch(reason => {
          console.error(`Failed to get extension capabilities.\n${reason}`);
          reject(reason);
        });
    });
  }

  static async setConfig(config: any) {
    requestAPI<any>('config', {
      method: 'POST',
      body: JSON.stringify(config)
    })
      .then(data => {
        //
      })
      .catch(reason => {
        console.error(`Failed to set NBI config.\n${reason}`);
      });
  }

  static async chatRequest(
    messageId: string,
    chatId: string,
    prompt: string,
    language: string,
    filename: string,
    additionalContext: IContextItem[],
    responseEmitter: IChatCompletionResponseEmitter
  ) {
    this._messageReceived.connect((_, msg) => {
      msg = JSON.parse(msg);
      if (msg.id === messageId) {
        responseEmitter.emit(msg);
      }
    });
    this._webSocket.send(
      JSON.stringify({
        id: messageId,
        type: RequestDataType.ChatRequest,
        data: { chatId, prompt, language, filename, additionalContext }
      })
    );
  }

  static async generateCode(
    chatId: string,
    prompt: string,
    prefix: string,
    suffix: string,
    existingCode: string,
    language: string,
    filename: string,
    responseEmitter: IChatCompletionResponseEmitter
  ) {
    const messageId = UUID.uuid4();
    this._messageReceived.connect((_, msg) => {
      msg = JSON.parse(msg);
      if (msg.id === messageId) {
        responseEmitter.emit(msg);
      }
    });
    this._webSocket.send(
      JSON.stringify({
        id: messageId,
        type: RequestDataType.GenerateCode,
        data: {
          chatId,
          prompt,
          prefix,
          suffix,
          existingCode,
          language,
          filename
        }
      })
    );
  }

  static async sendChatUserInput(messageId: string, data: any) {
    this._webSocket.send(
      JSON.stringify({
        id: messageId,
        type: RequestDataType.ChatUserInput,
        data
      })
    );
  }

  static async sendWebSocketMessage(
    messageId: string,
    messageType: RequestDataType,
    data: any
  ) {
    this._webSocket.send(
      JSON.stringify({ id: messageId, type: messageType, data })
    );
  }

  static async inlineCompletionsRequest(
    chatId: string,
    messageId: string,
    prefix: string,
    suffix: string,
    language: string,
    filename: string,
    responseEmitter: IChatCompletionResponseEmitter
  ) {
    this._messageReceived.connect((_, msg) => {
      msg = JSON.parse(msg);
      if (msg.id === messageId) {
        responseEmitter.emit(msg);
      }
    });
    this._webSocket.send(
      JSON.stringify({
        id: messageId,
        type: RequestDataType.InlineCompletionRequest,
        data: {
          chatId,
          prefix,
          suffix,
          language,
          filename
        }
      })
    );
  }
}
