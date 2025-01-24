// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, {
  ChangeEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import { UUID } from '@lumino/coreutils';

import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';

import { GitHubCopilot, GitHubCopilotLoginStatus } from './github-copilot';
import {
  BackendMessageType,
  ContextType,
  IActiveDocumentInfo,
  ICellContents,
  IChatCompletionResponseEmitter,
  IContextItem,
  RequestDataType,
  ResponseStreamDataType
} from './tokens';
import { JupyterFrontEnd } from '@jupyterlab/application';
import { requestAPI } from './handler';
import { MarkdownRenderer } from './markdown-renderer';

import copySvgstr from '../style/icons/copy.svg';
import copilotSvgstr from '../style/icons/copilot.svg';
import copilotWarningSvgstr from '../style/icons/copilot-warning.svg';
import { VscSend, VscStopCircle, VscEye, VscEyeClosed } from 'react-icons/vsc';
import { extractCodeFromMarkdown, isDarkTheme } from './utils';

export enum RunChatCompletionType {
  Chat,
  ExplainThis,
  FixThis,
  GenerateCode,
  ExplainThisOutput,
  TroubleshootThisOutput
}

export interface IRunChatCompletionRequest {
  messageId: string;
  chatId: string;
  type: RunChatCompletionType;
  content: string;
  language?: string;
  filename?: string;
  parentDirectory?: string;
  prefix?: string;
  suffix?: string;
  existingCode?: string;
  additionalContext?: IContextItem[];
}

export interface IChatSidebarOptions {
  getActiveDocumentInfo: () => IActiveDocumentInfo;
  getActiveSelectionContent: () => string;
  getCurrentCellContents: () => ICellContents;
  openFile: (path: string) => void;
  getApp: () => JupyterFrontEnd;
}

export class ChatSidebar extends ReactWidget {
  constructor(options: IChatSidebarOptions) {
    super();

    this._options = options;
    this.node.style.height = '100%';
  }

  render(): JSX.Element {
    return (
      <SidebarComponent
        getActiveDocumentInfo={this._options.getActiveDocumentInfo}
        getActiveSelectionContent={this._options.getActiveSelectionContent}
        getCurrentCellContents={this._options.getCurrentCellContents}
        openFile={this._options.openFile}
        getApp={this._options.getApp}
      />
    );
  }

  private _options: IChatSidebarOptions;
}

export interface IInlinePromptWidgetOptions {
  prompt: string;
  existingCode: string;
  prefix: string;
  suffix: string;
  onRequestSubmitted: (prompt: string) => void;
  onRequestCancelled: () => void;
  onContentStream: (content: string) => void;
  onContentStreamEnd: () => void;
  onUpdatedCodeChange: (content: string) => void;
  onUpdatedCodeAccepted: () => void;
}

export class InlinePromptWidget extends ReactWidget {
  constructor(rect: DOMRect, options: IInlinePromptWidgetOptions) {
    super();

    this.node.style.boxShadow = 'rgba(90, 76, 191, 0.8) 0px 0px 4px 4px';
    this.node.style.top = `${rect.top + 32}px`;
    this.node.style.left = `${rect.left}px`;
    this.node.style.zIndex = '1000';
    this.node.style.width = rect.width + 'px';
    this.node.style.height = '42px';
    this.node.style.border = '1px solid var(--jp-border-color0)';
    this._options = options;

    this.node.addEventListener('focusout', (event: any) => {
      if (this.node.contains(event.relatedTarget)) {
        return;
      }

      this._options.onRequestCancelled();
    });
  }

  updatePosition(rect: DOMRect) {
    this.node.style.top = `${rect.top + 32}px`;
    this.node.style.left = `${rect.left}px`;
    this.node.style.width = rect.width + 'px';
  }

  _onResponse(response: any) {
    if (response.type === BackendMessageType.StreamMessage) {
      const delta = response.data['choices']?.[0]?.['delta'];
      if (!delta) {
        return;
      }
      const responseMessage =
        response.data['choices']?.[0]?.['delta']?.['content'];
      if (!responseMessage) {
        return;
      }
      this._options.onContentStream(responseMessage);
    } else if (response.type === BackendMessageType.StreamEnd) {
      this._options.onContentStreamEnd();
    }
  }

  _onRequestSubmitted(prompt: string) {
    // code update
    if (this._options.existingCode !== '') {
      this.node.style.height = '300px';
    }
    // save the prompt in case of a rerender
    this._options.prompt = prompt;
    this._options.onRequestSubmitted(prompt);
  }

  render(): JSX.Element {
    return (
      <InlinePopoverComponent
        prompt={this._options.prompt}
        existingCode={this._options.existingCode}
        onRequestSubmitted={this._onRequestSubmitted.bind(this)}
        onRequestCancelled={this._options.onRequestCancelled}
        onResponseEmit={this._onResponse.bind(this)}
        prefix={this._options.prefix}
        suffix={this._options.suffix}
        onUpdatedCodeChange={this._options.onUpdatedCodeChange}
        onUpdatedCodeAccepted={this._options.onUpdatedCodeAccepted}
      />
    );
  }

  private _options: IInlinePromptWidgetOptions;
}

export class GitHubCopilotStatusBarItem extends ReactWidget {
  constructor(options: { getApp: () => JupyterFrontEnd }) {
    super();

    this._getApp = options.getApp;
  }

  render(): JSX.Element {
    return <GitHubCopilotStatusComponent getApp={this._getApp} />;
  }

  private _getApp: () => JupyterFrontEnd;
}

export class GitHubCopilotLoginDialogBody extends ReactWidget {
  constructor(options: { onLoggedIn: () => void }) {
    super();

    this._onLoggedIn = options.onLoggedIn;
  }

  render(): JSX.Element {
    return (
      <GitHubCopilotLoginDialogBodyComponent
        onLoggedIn={() => this._onLoggedIn()}
      />
    );
  }

  private _onLoggedIn: () => void;
}

interface IChatMessageContent {
  id: string;
  type: ResponseStreamDataType;
  content: any;
}

interface IChatMessage {
  id: string;
  parentId?: string;
  date: Date;
  from: string; // 'user' | 'copilot';
  contents: IChatMessageContent[];
  notebookLink?: string;
  participant?: IChatParticipant;
}

interface IChatParticipant {
  id: string;
  name: string;
  description: string;
  iconPath: string;
  commands: string[];
}

const answeredForms = new Map<string, string>();

function ChatResponseHTMLFrame(props: any) {
  const iframSrc = useMemo(
    () => URL.createObjectURL(new Blob([props.source], { type: 'text/html' })),
    []
  );
  return (
    <div className="chat-response-html-frame" key={`key-${props.index}`}>
      <iframe
        className="chat-response-html-frame-iframe"
        height={props.height}
        sandbox="allow-scripts"
        src={iframSrc}
      ></iframe>
    </div>
  );
}

function ChatResponse(props: any) {
  const msg: IChatMessage = props.message;
  const timestamp = msg.date.toLocaleTimeString('en-US', { hour12: false });

  const openNotebook = (event: any) => {
    const notebookPath = event.target.dataset['ref'];
    props.openFile(notebookPath);
  };

  const markFormConfirmed = (messageId: string) => {
    answeredForms.set(messageId, 'confirmed');
  };
  const markFormCanceled = (messageId: string) => {
    answeredForms.set(messageId, 'canceled');
  };

  const runCommand = (commandId: string, args: any) => {
    props.getApp().commands.execute(commandId, args);
  };

  // group messages by type
  const groupedContents: IChatMessageContent[] = [];
  let lastItemType: ResponseStreamDataType | undefined;

  for (let i = 0; i < msg.contents.length; i++) {
    const item = msg.contents[i];
    if (
      item.type === lastItemType &&
      lastItemType === ResponseStreamDataType.MarkdownPart
    ) {
      const lastItem = groupedContents[groupedContents.length - 1];
      lastItem.content += item.content;
    } else {
      groupedContents.push(structuredClone(item));
      lastItemType = item.type;
    }
  }

  return (
    <div className={`chat-message chat-message-${msg.from}`}>
      <div className="chat-message-header">
        <div className="chat-message-from">
          {msg.participant?.iconPath && (
            <div
              className={`chat-message-from-icon ${msg.participant?.id === 'default' ? 'chat-message-from-icon-default' : ''} ${isDarkTheme() ? 'dark' : ''}`}
            >
              <img src={msg.participant.iconPath} />
            </div>
          )}
          <div className="chat-message-from-title">
            {msg.from === 'user' ? 'User' : msg.participant?.name || 'Copilot'}
          </div>
          <div
            className="chat-message-from-progress"
            style={{ display: `${props.showGenerating ? 'visible' : 'none'}` }}
          >
            <div className="loading-ellipsis">Generating</div>
          </div>
        </div>
        <div className="chat-message-timestamp">{timestamp}</div>
      </div>
      <div className="chat-message-content">
        {groupedContents.map((item, index) => {
          switch (item.type) {
            case ResponseStreamDataType.Markdown:
            case ResponseStreamDataType.MarkdownPart:
              return (
                <MarkdownRenderer key={`key-${index}`} getApp={props.getApp}>
                  {item.content}
                </MarkdownRenderer>
              );
            case ResponseStreamDataType.HTMLFrame:
              return (
                <ChatResponseHTMLFrame
                  index={index}
                  source={item.content.source}
                  height={item.content.height}
                />
              );
            case ResponseStreamDataType.Button:
              return (
                <div className="chat-response-button">
                  <button
                    key={`key-${index}`}
                    className="jp-Dialog-button jp-mod-accept jp-mod-styled"
                    onClick={() =>
                      runCommand(item.content.commandId, item.content.args)
                    }
                  >
                    <div className="jp-Dialog-buttonLabel">
                      {item.content.title}
                    </div>
                  </button>
                </div>
              );
            case ResponseStreamDataType.Anchor:
              return (
                <div className="chat-response-anchor">
                  <a
                    key={`key-${index}`}
                    href={item.content.uri}
                    target="_blank"
                  >
                    {item.content.title}
                  </a>
                </div>
              );
            case ResponseStreamDataType.Progress:
              // show only if no more message available
              return index === groupedContents.length - 1 ? (
                <div key={`key-${index}`}>&#x2713; {item.content}</div>
              ) : null;
            case ResponseStreamDataType.Confirmation:
              return answeredForms.get(item.id) ===
                'confirmed' ? null : answeredForms.get(item.id) ===
                'canceled' ? (
                <div>&#10006; Canceled</div>
              ) : (
                <div className="chat-confirmation-form" key={`key-${index}`}>
                  {item.content.title ? (
                    <div>
                      <b>{item.content.title}</b>
                    </div>
                  ) : null}
                  {item.content.message ? (
                    <div>{item.content.message}</div>
                  ) : null}
                  <button
                    className="jp-Dialog-button jp-mod-accept jp-mod-styled"
                    onClick={() => {
                      markFormConfirmed(item.id);
                      runCommand(
                        'notebook-intelligence:chat-user-input',
                        item.content.confirmArgs
                      );
                    }}
                  >
                    <div className="jp-Dialog-buttonLabel">Proceed</div>
                  </button>
                  <button
                    className="jp-Dialog-button jp-mod-reject jp-mod-styled"
                    onClick={() => {
                      markFormCanceled(item.id);
                      runCommand(
                        'notebook-intelligence:chat-user-input',
                        item.content.cancelArgs
                      );
                    }}
                  >
                    <div className="jp-Dialog-buttonLabel">Cancel</div>
                  </button>
                </div>
              );
          }
          return null;
        })}

        {msg.notebookLink && (
          <a
            className="copilot-generated-notebook-link"
            data-ref={msg.notebookLink}
            onClick={openNotebook}
          >
            open notebook
          </a>
        )}
      </div>
    </div>
  );
}

async function submitCompletionRequest(
  request: IRunChatCompletionRequest,
  responseEmitter: IChatCompletionResponseEmitter
): Promise<any> {
  switch (request.type) {
    case RunChatCompletionType.Chat:
      return GitHubCopilot.chatRequest(
        request.messageId,
        request.chatId,
        request.content,
        request.language || 'python',
        request.filename || 'Untitled.ipynb',
        request.additionalContext || [],
        responseEmitter
      );
    case RunChatCompletionType.ExplainThis:
    case RunChatCompletionType.FixThis:
    case RunChatCompletionType.ExplainThisOutput:
    case RunChatCompletionType.TroubleshootThisOutput: {
      return GitHubCopilot.chatRequest(
        request.messageId,
        request.chatId,
        request.content,
        request.language || 'python',
        request.filename || 'Untitled.ipynb',
        [],
        responseEmitter
      );
    }
    case RunChatCompletionType.GenerateCode:
      return GitHubCopilot.generateCode(
        request.chatId,
        request.content,
        request.prefix || '',
        request.suffix || '',
        request.existingCode || '',
        request.language || 'python',
        request.filename || 'Untitled.ipynb',
        responseEmitter
      );
  }
}

function SidebarComponent(props: any) {
  const [chatMessages, setChatMessages] = useState<IChatMessage[]>([]);
  const [prompt, setPrompt] = useState<string>('');
  const [draftPrompt, setDraftPrompt] = useState<string>('');
  const messagesEndRef = useRef<null | HTMLDivElement>(null);
  const [ghLoginStatus, setGHLoginStatus] = useState(
    GitHubCopilotLoginStatus.NotLoggedIn
  );
  const [loginClickCount, _setLoginClickCount] = useState(0);
  const [copilotRequestInProgress, setCopilotRequestInProgress] =
    useState(false);
  const [showPopover, setShowPopover] = useState(false);
  const [originalPrefixes, setOriginalPrefixes] = useState<string[]>([]);
  const [prefixSuggestions, setPrefixSuggestions] = useState<string[]>([]);
  const [selectedPrefixSuggestionIndex, setSelectedPrefixSuggestionIndex] =
    useState(0);
  const promptInputRef = useRef<HTMLTextAreaElement>(null);
  const [promptHistory, setPromptHistory] = useState<string[]>([]);
  // position on prompt history stack
  const [promptHistoryIndex, setPromptHistoryIndex] = useState(0);
  const [chatId, setChatId] = useState(UUID.uuid4());
  const lastMessageId = useRef<string>('');
  const chatParticipants = useRef<IChatParticipant[]>([]);
  const [contextOn, setContextOn] = useState(false);
  const [activeDocumentInfo, setActiveDocumentInfo] =
    useState<IActiveDocumentInfo | null>(null);
  const [currentFileContextTitle, setCurrentFileContextTitle] = useState('');

  useEffect(() => {
    requestAPI<any>('capabilities', { method: 'GET' })
      .then(data => {
        chatParticipants.current = structuredClone(data.chat_participants);
        const prefixes: string[] = [];
        for (const participant of data.chat_participants) {
          const id = participant.id;
          const commands = participant.commands;
          const participantPrefix = id === 'default' ? '' : `@${id}`;
          if (participantPrefix !== '') {
            prefixes.push(participantPrefix);
          }
          const commandPrefix =
            participantPrefix === '' ? '' : `${participantPrefix} `;
          for (const command of commands) {
            prefixes.push(`${commandPrefix}/${command}`);
          }
        }
        setOriginalPrefixes(prefixes);
        setPrefixSuggestions(prefixes);
      })
      .catch(reason => {
        console.error(
          `The notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
  }, []);

  useEffect(() => {
    const fetchData = () => {
      setGHLoginStatus(GitHubCopilot.getLoginStatus());
    };

    fetchData();

    const intervalId = setInterval(fetchData, 1000);

    return () => clearInterval(intervalId);
  }, [loginClickCount]);

  useEffect(() => {
    setSelectedPrefixSuggestionIndex(0);
  }, [prefixSuggestions]);

  const onPromptChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const newPrompt = event.target.value;
    setPrompt(newPrompt);
    const trimmedPrompt = newPrompt.trimStart();
    if (trimmedPrompt === '@' || trimmedPrompt === '/') {
      setShowPopover(true);
      filterPrefixSuggestions(trimmedPrompt);
    } else if (
      trimmedPrompt.startsWith('@') ||
      trimmedPrompt.startsWith('/') ||
      trimmedPrompt === ''
    ) {
      filterPrefixSuggestions(trimmedPrompt);
    } else {
      setShowPopover(false);
    }
  };

  const applyPrefixSuggestion = (prefix: string) => {
    if (prefix.includes(prompt)) {
      setPrompt(`${prefix} `);
    } else {
      setPrompt(`${prefix} ${prompt} `);
    }
    setShowPopover(false);
    promptInputRef.current?.focus();
    setSelectedPrefixSuggestionIndex(0);
  };

  const prefixSuggestionSelected = (event: any) => {
    const prefix = event.target.dataset['value'];
    applyPrefixSuggestion(prefix);
  };

  const handleSubmitStopChatButtonClick = async () => {
    if (!copilotRequestInProgress) {
      handleUserInputSubmit();
    } else {
      handleUserInputCancel();
    }
  };

  const handleUserInputSubmit = async () => {
    setPromptHistoryIndex(promptHistory.length + 1);
    setPromptHistory([...promptHistory, prompt]);
    setShowPopover(false);

    const promptPrefixParts = [];
    const promptParts = prompt.split(' ');
    if (promptParts.length > 1) {
      for (let i = 0; i < Math.min(promptParts.length, 2); i++) {
        const part = promptParts[i];
        if (part.startsWith('@') || part.startsWith('/')) {
          promptPrefixParts.push(part);
        }
      }
    }

    const promptPrefix =
      promptPrefixParts.length > 0 ? promptPrefixParts.join(' ') + ' ' : '';

    lastMessageId.current = UUID.uuid4();

    const newList = [
      ...chatMessages,
      {
        id: lastMessageId.current,
        date: new Date(),
        from: 'user',
        contents: [
          {
            id: lastMessageId.current,
            type: ResponseStreamDataType.Markdown,
            content: prompt
          }
        ]
      }
    ];
    setChatMessages(newList);

    if (prompt.startsWith('/clear')) {
      setChatMessages([]);
      setPrompt('');
      resetChatId();
      resetPrefixSuggestions();
      setPromptHistory([]);
      setPromptHistoryIndex(0);
      GitHubCopilot.sendWebSocketMessage(
        UUID.uuid4(),
        RequestDataType.ClearChatHistory,
        { chatId }
      );
      return;
    }

    setCopilotRequestInProgress(true);

    const activeDocInfo: IActiveDocumentInfo = props.getActiveDocumentInfo();
    const extractedPrompt = prompt;
    const parentDirectory = activeDocInfo.parentDirectory!;
    const contents: IChatMessageContent[] = [];
    const app = props.getApp();
    const additionalContext: IContextItem[] = [];
    if (contextOn && activeDocumentInfo) {
      additionalContext.push({
        type: ContextType.CurrentFile,
        content: props.getActiveSelectionContent(),
        currentCellContents: props.getCurrentCellContents(),
        filePath: activeDocumentInfo.filePath,
        cellIndex: activeDocumentInfo.activeCellIndex,
        startLine: activeDocumentInfo.selection.start.line + 1,
        endLine: activeDocumentInfo.selection.end.line + 1
      });
    }

    submitCompletionRequest(
      {
        messageId: lastMessageId.current,
        chatId,
        type: RunChatCompletionType.Chat,
        content: extractedPrompt,
        language: activeDocInfo.language,
        filename: activeDocInfo.filename,
        parentDirectory,
        additionalContext
      },
      {
        emit: async response => {
          if (response.id !== lastMessageId.current) {
            return;
          }

          let responseMessage = '';
          if (response.type === BackendMessageType.StreamMessage) {
            const delta = response.data['choices']?.[0]?.['delta'];
            if (!delta) {
              return;
            }
            if (delta['nbiContent']) {
              const nbiContent = delta['nbiContent'];
              contents.push({
                id: response.id,
                type: nbiContent.type,
                content: nbiContent.content
              });
            } else {
              responseMessage =
                response.data['choices']?.[0]?.['delta']?.['content'];
              if (!responseMessage) {
                return;
              }
              contents.push({
                id: response.id,
                type: ResponseStreamDataType.MarkdownPart,
                content: responseMessage
              });
            }
          } else if (response.type === BackendMessageType.StreamEnd) {
            setCopilotRequestInProgress(false);
          } else if (response.type === BackendMessageType.RunUICommand) {
            const messageId = response.id;
            const result = await app.commands.execute(
              response.data.commandId,
              response.data.args
            );
            const data = {
              callback_id: response.data.callback_id,
              result
            };
            GitHubCopilot.sendWebSocketMessage(
              messageId,
              RequestDataType.RunUICommandResponse,
              data
            );
          }
          setChatMessages([
            ...newList,
            {
              id: UUID.uuid4(),
              date: new Date(),
              from: 'copilot',
              contents: contents,
              participant: chatParticipants.current?.find(participant => {
                return participant.id === response.participant;
              })
            }
          ]);
        }
      }
    );
    setPrompt(promptPrefix);
    filterPrefixSuggestions(promptPrefix);
  };

  const handleUserInputCancel = async () => {
    GitHubCopilot.sendWebSocketMessage(
      lastMessageId.current,
      RequestDataType.CancelChatRequest,
      { chatId }
    );

    lastMessageId.current = '';
    setCopilotRequestInProgress(false);
  };

  const filterPrefixSuggestions = (prmpt: string) => {
    const userInput = prmpt.trimStart();
    if (userInput === '') {
      setPrefixSuggestions(originalPrefixes);
    } else {
      setPrefixSuggestions(
        originalPrefixes.filter(prefix => prefix.includes(userInput))
      );
    }
  };

  const resetPrefixSuggestions = () => {
    setPrefixSuggestions(originalPrefixes);
    setSelectedPrefixSuggestionIndex(0);
  };
  const resetChatId = () => {
    setChatId(UUID.uuid4());
  };

  const onPromptKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter') {
      event.stopPropagation();
      event.preventDefault();
      if (showPopover) {
        applyPrefixSuggestion(prefixSuggestions[selectedPrefixSuggestionIndex]);
        return;
      }

      setSelectedPrefixSuggestionIndex(0);
      handleSubmitStopChatButtonClick();
    } else if (event.key === 'Tab') {
      if (showPopover) {
        event.stopPropagation();
        event.preventDefault();
        applyPrefixSuggestion(prefixSuggestions[selectedPrefixSuggestionIndex]);
        return;
      }
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      event.preventDefault();
      setShowPopover(false);
      setSelectedPrefixSuggestionIndex(0);
    } else if (event.key === 'ArrowUp') {
      event.stopPropagation();
      event.preventDefault();

      if (showPopover) {
        setSelectedPrefixSuggestionIndex(
          (selectedPrefixSuggestionIndex - 1 + prefixSuggestions.length) %
            prefixSuggestions.length
        );
        return;
      }

      setShowPopover(false);
      // first time up key press
      if (
        promptHistory.length > 0 &&
        promptHistoryIndex === promptHistory.length
      ) {
        setDraftPrompt(prompt);
      }

      if (
        promptHistory.length > 0 &&
        promptHistoryIndex > 0 &&
        promptHistoryIndex <= promptHistory.length
      ) {
        const prevPrompt = promptHistory[promptHistoryIndex - 1];
        const newIndex = promptHistoryIndex - 1;
        setPrompt(prevPrompt);
        setPromptHistoryIndex(newIndex);
      }
    } else if (event.key === 'ArrowDown') {
      event.stopPropagation();
      event.preventDefault();

      if (showPopover) {
        setSelectedPrefixSuggestionIndex(
          (selectedPrefixSuggestionIndex + 1 + prefixSuggestions.length) %
            prefixSuggestions.length
        );
        return;
      }

      setShowPopover(false);
      if (
        promptHistory.length > 0 &&
        promptHistoryIndex >= 0 &&
        promptHistoryIndex < promptHistory.length
      ) {
        if (promptHistoryIndex === promptHistory.length - 1) {
          setPrompt(draftPrompt);
          setPromptHistoryIndex(promptHistory.length);
          return;
        }
        const prevPrompt = promptHistory[promptHistoryIndex + 1];
        const newIndex = promptHistoryIndex + 1;
        setPrompt(prevPrompt);
        setPromptHistoryIndex(newIndex);
      }
    }
  };

  const scrollMessagesToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleLoginClick = async () => {
    props
      .getApp()
      .commands.execute(
        'notebook-intelligence:open-github-copilot-login-dialog'
      );
  };

  useEffect(() => {
    scrollMessagesToBottom();
  }, [copilotRequestInProgress]);

  const promptRequestHandler = useCallback(
    (eventData: any) => {
      const request: IRunChatCompletionRequest = eventData.detail;
      request.chatId = chatId;
      let message = '';
      switch (request.type) {
        case RunChatCompletionType.ExplainThis:
          message = `Explain this code:\n\`\`\`\n${request.content}\n\`\`\`\n`;
          break;
        case RunChatCompletionType.FixThis:
          message = `Fix this code:\n\`\`\`\n${request.content}\n\`\`\`\n`;
          break;
        case RunChatCompletionType.ExplainThisOutput:
          message = `Explain this notebook cell output: \n\`\`\`\n${request.content}\n\`\`\`\n`;
          break;
        case RunChatCompletionType.TroubleshootThisOutput:
          message = `Troubleshoot errors reported in the notebook cell output: \n\`\`\`\n${request.content}\n\`\`\`\n`;
          break;
      }
      const messageId = UUID.uuid4();
      request.messageId = messageId;
      const newList = [
        ...chatMessages,
        {
          id: messageId,
          date: new Date(),
          from: 'user',
          contents: [
            {
              id: messageId,
              type: ResponseStreamDataType.Markdown,
              content: message
            }
          ]
        }
      ];
      setChatMessages(newList);

      setCopilotRequestInProgress(true);

      const contents: IChatMessageContent[] = [];

      submitCompletionRequest(request, {
        emit: response => {
          if (response.type === BackendMessageType.StreamMessage) {
            const delta = response.data['choices']?.[0]?.['delta'];
            if (!delta) {
              return;
            }

            const responseMessage =
              response.data['choices']?.[0]?.['delta']?.['content'];
            if (!responseMessage) {
              return;
            }
            contents.push({
              id: response.id,
              type: ResponseStreamDataType.MarkdownPart,
              content: responseMessage
            });
          } else if (response.type === BackendMessageType.StreamEnd) {
            setCopilotRequestInProgress(false);
          }
          const messageId = UUID.uuid4();
          setChatMessages([
            ...newList,
            {
              id: messageId,
              date: new Date(),
              from: 'copilot',
              contents: contents,
              participant: chatParticipants.current?.find(participant => {
                return participant.id === response.participant;
              })
            }
          ]);
        }
      });
    },
    [chatMessages]
  );

  useEffect(() => {
    document.addEventListener('copilotSidebar:runPrompt', promptRequestHandler);

    return () => {
      document.removeEventListener(
        'copilotSidebar:runPrompt',
        promptRequestHandler
      );
    };
  }, [chatMessages]);

  const activeDocumentChangeHandler = (eventData: any) => {
    // if file changes reset the context toggle
    if (
      eventData.detail.activeDocumentInfo?.filePath !==
      activeDocumentInfo?.filePath
    ) {
      setContextOn(false);
    }
    setActiveDocumentInfo({
      ...eventData.detail.activeDocumentInfo,
      ...{ activeWidget: null }
    });
    setCurrentFileContextTitle(
      getActiveDocumentContextTitle(eventData.detail.activeDocumentInfo)
    );
  };

  useEffect(() => {
    document.addEventListener(
      'copilotSidebar:activeDocumentChanged',
      activeDocumentChangeHandler
    );

    return () => {
      document.removeEventListener(
        'copilotSidebar:activeDocumentChanged',
        activeDocumentChangeHandler
      );
    };
  }, [activeDocumentInfo]);

  const getActiveDocumentContextTitle = (
    activeDocumentInfo: IActiveDocumentInfo
  ): string => {
    if (!activeDocumentInfo) {
      return '';
    }
    const wholeFile =
      activeDocumentInfo.selection === null ||
      (activeDocumentInfo.selection.start.line ===
        activeDocumentInfo.selection.end.line &&
        activeDocumentInfo.selection.start.column ===
          activeDocumentInfo.selection.end.column);
    let cellAndLineIndicator = '';

    if (!wholeFile) {
      if (activeDocumentInfo.filename.endsWith('.ipynb')) {
        cellAndLineIndicator = ` · Cell ${activeDocumentInfo.activeCellIndex + 1}`;
      }
      if (
        activeDocumentInfo.selection.start.line ===
        activeDocumentInfo.selection.end.line
      ) {
        cellAndLineIndicator += `:${activeDocumentInfo.selection.start.line + 1}`;
      } else {
        cellAndLineIndicator += `:${activeDocumentInfo.selection.start.line + 1}-${activeDocumentInfo.selection.end.line + 1}`;
      }
    }

    return `${activeDocumentInfo.filename}${cellAndLineIndicator}`;
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">Copilot Chat</div>
      </div>
      {ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn && (
        <div className="sidebar-login-info">
          <div>
            You are not logged in to GitHub Copilot. Please login now to
            activate chat.
          </div>
          <div>
            <button
              className="jp-Dialog-button jp-mod-accept jp-mod-styled"
              onClick={handleLoginClick}
            >
              <div className="jp-Dialog-buttonLabel">
                Login to GitHub Copilot
              </div>
            </button>
          </div>
        </div>
      )}

      {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn &&
        (chatMessages.length === 0 ? (
          <div className="sidebar-messages">
            <div className="sidebar-greeting">
              Welcome! How can I assist you today?
            </div>
          </div>
        ) : (
          <div className="sidebar-messages">
            {chatMessages.map((msg, index) => (
              <ChatResponse
                key={`key-${index}`}
                message={msg}
                openFile={props.openFile}
                getApp={props.getApp}
                showGenerating={
                  index === chatMessages.length - 1 &&
                  msg.from === 'copilot' &&
                  copilotRequestInProgress
                }
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        ))}
      {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn && (
        <div className="sidebar-user-input">
          <textarea
            ref={promptInputRef}
            rows={3}
            onChange={onPromptChange}
            onKeyDown={onPromptKeyDown}
            placeholder="Ask Copilot..."
            spellCheck={false}
            value={prompt}
          />
          {activeDocumentInfo?.filename && (
            <div className="user-input-context-row">
              <div
                className={`user-input-context user-input-context-active-file ${contextOn ? 'on' : 'off'}`}
              >
                <div>{currentFileContextTitle}</div>
                {contextOn ? (
                  <VscEye
                    onClick={() => setContextOn(!contextOn)}
                    title="Use as context"
                  />
                ) : (
                  <VscEyeClosed
                    onClick={() => setContextOn(!contextOn)}
                    title="Don't use as context"
                  />
                )}
              </div>
            </div>
          )}
          <div className="user-input-footer">
            <div>
              <a
                href="javascript:void(0)"
                onClick={() => {
                  setShowPopover(true);
                  promptInputRef.current?.focus();
                }}
                title="Select chat participant"
              >
                @
              </a>
            </div>
            <div style={{ flexGrow: 1 }}></div>
            <div>
              <button
                className="jp-Dialog-button jp-mod-accept jp-mod-styled send-button"
                onClick={() => handleSubmitStopChatButtonClick()}
                disabled={prompt.length === 0 && !copilotRequestInProgress}
              >
                {copilotRequestInProgress ? <VscStopCircle /> : <VscSend />}
              </button>
            </div>
          </div>
          {showPopover && prefixSuggestions.length > 0 && (
            <div className="user-input-autocomplete">
              {prefixSuggestions.map((prefix, index) => (
                <div
                  key={`key-${index}`}
                  className={`user-input-autocomplete-item ${index === selectedPrefixSuggestionIndex ? 'selected' : ''}`}
                  data-value={prefix}
                  onClick={event => prefixSuggestionSelected(event)}
                >
                  {prefix}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InlinePopoverComponent(props: any) {
  const [modifiedCode, setModifiedCode] = useState<string>('');
  const [promptSubmitted, setPromptSubmitted] = useState(false);
  const originalOnRequestSubmitted = props.onRequestSubmitted;
  const originalOnResponseEmit = props.onResponseEmit;

  const onRequestSubmitted = (prompt: string) => {
    setModifiedCode('');
    setPromptSubmitted(true);
    originalOnRequestSubmitted(prompt);
  };

  const onResponseEmit = (response: any) => {
    if (response.type === BackendMessageType.StreamMessage) {
      const delta = response.data['choices']?.[0]?.['delta'];
      if (!delta) {
        return;
      }
      const responseMessage =
        response.data['choices']?.[0]?.['delta']?.['content'];
      if (!responseMessage) {
        return;
      }
      setModifiedCode((modifiedCode: string) => modifiedCode + responseMessage);
    } else if (response.type === BackendMessageType.StreamEnd) {
      setModifiedCode((modifiedCode: string) =>
        extractCodeFromMarkdown(modifiedCode)
      );
    }

    originalOnResponseEmit(response);
  };

  return (
    <div className="inline-popover">
      <InlinePromptComponent
        {...props}
        onRequestSubmitted={onRequestSubmitted}
        onResponseEmit={onResponseEmit}
        onUpdatedCodeAccepted={props.onUpdatedCodeAccepted}
        limitHeight={props.existingCode !== '' && promptSubmitted}
      />
      {props.existingCode !== '' && promptSubmitted && (
        <>
          <InlineDiffViewerComponent {...props} modifiedCode={modifiedCode} />
          <div className="inline-popover-footer">
            <div>
              <button
                className="jp-Button jp-mod-accept jp-mod-styled jp-mod-small"
                onClick={() => props.onUpdatedCodeAccepted()}
              >
                Accept
              </button>
            </div>
            <div>
              <button
                className="jp-Button jp-mod-reject jp-mod-styled jp-mod-small"
                onClick={() => props.onRequestCancelled()}
              >
                Cancel
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function InlineDiffViewerComponent(props: any) {
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const [diffEditor, setDiffEditor] =
    useState<monaco.editor.IStandaloneDiffEditor>(null);

  useEffect(() => {
    const editorEl = editorContainerRef.current;
    editorEl.className = 'monaco-editor-container';

    const existingModel = monaco.editor.createModel(
      props.existingCode,
      'text/plain'
    );
    const modifiedModel = monaco.editor.createModel(
      props.modifiedCode,
      'text/plain'
    );

    const editor = monaco.editor.createDiffEditor(editorEl, {
      originalEditable: false,
      automaticLayout: true,
      theme: isDarkTheme() ? 'vs-dark' : 'vs'
    });
    editor.setModel({
      original: existingModel,
      modified: modifiedModel
    });
    modifiedModel.onDidChangeContent(() => {
      props.onUpdatedCodeChange(modifiedModel.getValue());
    });
    setDiffEditor(editor);
  }, []);

  useEffect(() => {
    diffEditor?.getModifiedEditor().getModel()?.setValue(props.modifiedCode);
  }, [props.modifiedCode]);

  return (
    <div ref={editorContainerRef} className="monaco-editor-container"></div>
  );
}

function InlinePromptComponent(props: any) {
  const [prompt, setPrompt] = useState<string>(props.prompt);
  const promptInputRef = useRef<HTMLTextAreaElement>(null);
  const [inputSubmitted, setInputSubmitted] = useState(false);

  const onPromptChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const newPrompt = event.target.value;
    setPrompt(newPrompt);
  };

  const handleUserInputSubmit = async () => {
    const promptPrefixParts = [];
    const promptParts = prompt.split(' ');
    if (promptParts.length > 1) {
      for (let i = 0; i < Math.min(promptParts.length, 2); i++) {
        const part = promptParts[i];
        if (part.startsWith('@') || part.startsWith('/')) {
          promptPrefixParts.push(part);
        }
      }
    }

    submitCompletionRequest(
      {
        messageId: UUID.uuid4(),
        chatId: UUID.uuid4(),
        type: RunChatCompletionType.GenerateCode,
        content: prompt,
        language: undefined,
        filename: undefined,
        parentDirectory: '',
        prefix: props.prefix,
        suffix: props.suffix,
        existingCode: props.existingCode
      },
      {
        emit: async response => {
          props.onResponseEmit(response);
        }
      }
    );

    setInputSubmitted(true);
  };

  const onPromptKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter') {
      event.stopPropagation();
      event.preventDefault();
      if (inputSubmitted && (event.metaKey || event.ctrlKey)) {
        props.onUpdatedCodeAccepted();
      } else {
        props.onRequestSubmitted(prompt);
        handleUserInputSubmit();
      }
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      event.preventDefault();
      props.onRequestCancelled();
    }
  };

  useEffect(() => {
    const input = promptInputRef.current;
    if (input) {
      input.select();
      promptInputRef.current?.focus();
    }
  }, []);

  return (
    <div
      className="inline-prompt-container"
      style={{ height: props.limitHeight ? '40px' : '100%' }}
    >
      <textarea
        ref={promptInputRef}
        rows={3}
        onChange={onPromptChange}
        onKeyDown={onPromptKeyDown}
        placeholder="Ask Copilot to generate Python code..."
        spellCheck={false}
        value={prompt}
      />
    </div>
  );
}

function GitHubCopilotStatusComponent(props: any) {
  const [ghLoginStatus, setGHLoginStatus] = useState(
    GitHubCopilotLoginStatus.NotLoggedIn
  );
  const [loginClickCount, _setLoginClickCount] = useState(0);

  useEffect(() => {
    const fetchData = () => {
      setGHLoginStatus(GitHubCopilot.getLoginStatus());
    };

    fetchData();

    const intervalId = setInterval(fetchData, 1000);

    return () => clearInterval(intervalId);
  }, [loginClickCount]);

  const onStatusClick = () => {
    props
      .getApp()
      .commands.execute(
        'notebook-intelligence:open-github-copilot-login-dialog'
      );
  };

  return (
    <div
      title={`GitHub Copilot: ${ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn ? 'Logged in' : 'Not logged in'}`}
      className="github-copilot-status-bar"
      onClick={() => onStatusClick()}
      dangerouslySetInnerHTML={{
        __html:
          ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn
            ? copilotSvgstr
            : copilotWarningSvgstr
      }}
    ></div>
  );
}

function GitHubCopilotLoginDialogBodyComponent(props: any) {
  const [ghLoginStatus, setGHLoginStatus] = useState(
    GitHubCopilotLoginStatus.NotLoggedIn
  );
  const [loginClickCount, setLoginClickCount] = useState(0);
  const [loginClicked, setLoginClicked] = useState(false);
  const [deviceActivationURL, setDeviceActivationURL] = useState('');
  const [deviceActivationCode, setDeviceActivationCode] = useState('');

  useEffect(() => {
    const fetchData = () => {
      const status = GitHubCopilot.getLoginStatus();
      setGHLoginStatus(status);
      if (status === GitHubCopilotLoginStatus.LoggedIn && loginClicked) {
        setTimeout(() => {
          props.onLoggedIn();
        }, 1000);
      }
    };

    fetchData();

    const intervalId = setInterval(fetchData, 1000);

    return () => clearInterval(intervalId);
  }, [loginClickCount]);

  const handleLoginClick = async () => {
    const response = await GitHubCopilot.loginToGitHub();
    setDeviceActivationURL((response as any).verificationURI);
    setDeviceActivationCode((response as any).userCode);
    setLoginClickCount(loginClickCount + 1);
    setLoginClicked(true);
  };

  const handleLogoutClick = async () => {
    await GitHubCopilot.logoutFromGitHub();
    setLoginClickCount(loginClickCount + 1);
  };

  const loggedIn = ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn;

  return (
    <div className="github-copilot-login-dialog">
      <div className="github-copilot-login-status">
        <h4>
          Login status:{' '}
          <span
            className={`github-copilot-login-status-text ${loggedIn ? 'logged-in' : ''}`}
          >
            {loggedIn
              ? 'Logged in'
              : ghLoginStatus === GitHubCopilotLoginStatus.LoggingIn
                ? 'Logging in...'
                : ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice
                  ? 'Activating device...'
                  : ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn
                    ? 'Not logged in'
                    : 'Unknown'}
          </span>
        </h4>
      </div>

      {ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn && (
        <>
          <div>
            Your GitHub tokens, code and data are directly transferred to GitHub
            Copilot as needed without storing any copies other than keeping in
            the process memory.
          </div>
          <div>
            <a href="https://github.com/features/copilot" target="_blank">
              GitHub Copilot
            </a>{' '}
            requires a subscription and it has a free tier. GitHub Copilot is
            subject to the{' '}
            <a
              href="https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features"
              target="_blank"
            >
              GitHub Terms for Additional Products and Features
            </a>
            .
          </div>
          <div>
            <h4>Privacy and terms</h4>
            By using Copilot Chat you agree to{' '}
            <a
              href="https://docs.github.com/en/copilot/responsible-use-of-github-copilot-features/responsible-use-of-github-copilot-chat-in-your-ide"
              target="_blank"
            >
              GitHub Copilot chat terms
            </a>
            . Review the terms to understand about usage, limitations and ways
            to improve Copilot Chat. Please review{' '}
            <a
              href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
              target="_blank"
            >
              Privacy Statement
            </a>
            .
          </div>
          <div>
            <button
              className="jp-Dialog-button jp-mod-accept jp-mod-reject jp-mod-styled"
              onClick={handleLoginClick}
            >
              <div className="jp-Dialog-buttonLabel">
                Login using your GitHub account
              </div>
            </button>
          </div>
        </>
      )}

      {loggedIn && (
        <div>
          <button
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={handleLogoutClick}
          >
            <div className="jp-Dialog-buttonLabel">Logout</div>
          </button>
        </div>
      )}

      {ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice &&
        deviceActivationURL &&
        deviceActivationCode && (
          <div>
            <div className="copilot-activation-message">
              Copy code{' '}
              <span
                className="user-code-span"
                onClick={() => {
                  navigator.clipboard.writeText(deviceActivationCode);
                  return true;
                }}
              >
                <b>
                  {deviceActivationCode}{' '}
                  <span
                    className="copy-icon"
                    dangerouslySetInnerHTML={{ __html: copySvgstr }}
                  ></span>
                </b>
              </span>{' '}
              and enter at{' '}
              <a href={deviceActivationURL} target="_blank">
                {deviceActivationURL}
              </a>{' '}
              to allow access to GitHub Copilot from this app. Activation could
              take up to a minute after you enter the code.
            </div>
          </div>
        )}

      {ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice && (
        <div style={{ marginTop: '10px' }}>
          <button
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={handleLogoutClick}
          >
            <div className="jp-Dialog-buttonLabel">Cancel activation</div>
          </button>
        </div>
      )}
    </div>
  );
}
