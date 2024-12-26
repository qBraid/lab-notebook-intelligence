// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { ChangeEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import Markdown from 'react-markdown';
import { UUID } from '@lumino/coreutils';

import { GitHubCopilot, GitHubCopilotLoginStatus } from './github-copilot';
import { IActiveDocumentInfo, IChatCompletionResponseEmitter, ResponseStreamDataType } from './tokens';
import { JupyterFrontEnd } from '@jupyterlab/application';

export enum RunChatCompletionType {
    Chat,
    ExplainThis,
    FixThis,
    NewNotebook,
}

export interface IRunChatCompletionRequest {
    type: RunChatCompletionType,
    content: string,
    language?: string,
    filename?: string,
    parentDirectory?: string,
}

export interface IChatSidebarOptions {
    getActiveDocumentInfo: () => IActiveDocumentInfo;
    openFile: (path: string) => void;
    getApp: () =>  JupyterFrontEnd<JupyterFrontEnd.IShell, "desktop" | "mobile">;
}

export class ChatSidebar extends ReactWidget {
    constructor(options: IChatSidebarOptions) {
        super();

        this.node.style.height = '100%';
        this._getActiveDocumentInfo = options.getActiveDocumentInfo;
        this._openFile = options.openFile;
        this._getApp = options.getApp;
    }

    render(): JSX.Element {
        return <SidebarComponent getActiveDocumentInfo={this._getActiveDocumentInfo} openFile={this._openFile} getApp={this._getApp} />;
    }

    private _getActiveDocumentInfo: () => IActiveDocumentInfo;
    private _openFile: (path: string) => void;
    private _getApp: () => JupyterFrontEnd<JupyterFrontEnd.IShell, "desktop" | "mobile">;
}

interface IChatMessageContent {
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
}

function ChatResponse(props: any) {
    const msg: IChatMessage = props.message;
    const timestamp = `${msg.date.getHours()}:${msg.date.getMinutes()}:${msg.date.getSeconds()}`;

    const openNotebook = (event: any) => {
        const notebookPath = event.target.dataset['ref'];
        props.openFile(notebookPath);
    };

    const runCommand = (commandId: string, args: any) => {
        props.getApp().commands.execute(commandId, args);
    };

    // group messages by type
    const groupedContents: IChatMessageContent[] = [];
    let lastItemType: ResponseStreamDataType | undefined;

    for (let i = 0; i < msg.contents.length; i++) {
        const item = msg.contents[i];
        if (item.type === lastItemType &&
            (lastItemType === ResponseStreamDataType.Markdown || lastItemType === ResponseStreamDataType.HTML)) {
            const lastItem = groupedContents[groupedContents.length - 1];
            lastItem.content += item.content;
        } else {
            groupedContents.push(structuredClone(item));
            lastItemType = item.type;
        }
    }

    return (
        <div className={`chat-message chat-message-${msg.from}`} >
            <div className="chat-message-header">
                <div className="chat-message-from">{msg.from === 'user' ? 'User' : 'Copilot'}</div>
                <div className="chat-message-timestamp">{timestamp}</div>
            </div>
            <div className="chat-message-content">
                {groupedContents.map((item, index) => {
                    switch (item.type) {
                        case ResponseStreamDataType.Markdown:
                            return <Markdown key={`key-${index}`}>{item.content}</Markdown>;
                        case ResponseStreamDataType.HTML:
                            return <div key={`key-${index}`} dangerouslySetInnerHTML={{__html: item.content}} />;
                        case ResponseStreamDataType.Button:
                            return <button key={`key-${index}`} onClick={() => runCommand(item.content.commandId, item.content.args)}>{item.content.title}</button>;
                        case ResponseStreamDataType.Anchor:
                            return <a key={`key-${index}`} href={item.content.uri} target="_blank">{item.content.title}</a>;
                        case ResponseStreamDataType.Progress:
                            // show only if no more message available
                            return (index === (groupedContents.length - 1)) ? <div key={`key-${index}`}>&#x2713; {item.content}</div> : null;
                        case ResponseStreamDataType.Confirmation:
                            return <div key={`key-${index}`}>
                                    {item.content.title ? <div><b>{item.content.title}</b></div> : null}
                                    {item.content.message ? <div>{item.content.message}</div> : null}
                                    <button onClick={() => runCommand('notebook-intelligence:chat_user_input', item.content.confirmArgs)}>Proceed</button>
                                    <button onClick={() => runCommand('notebook-intelligence:chat_user_input', item.content.cancelArgs)}>Cancel</button>
                                </div>;
                    }
                    return null;
                })}

                {msg.notebookLink && (
                    <a className="copilot-generated-notebook-link" data-ref={msg.notebookLink} onClick={openNotebook}>open notebook</a>
                )}
            </div>
        </div>
    );
}

async function submitCompletionRequest(request: IRunChatCompletionRequest, responseEmitter: IChatCompletionResponseEmitter): Promise<any> {
    switch (request.type) {
        case RunChatCompletionType.Chat:
            return GitHubCopilot.chatRequest(
                request.content,
                request.language || 'python',
                request.filename || 'Untitled.ipynb',
                responseEmitter
            );
        case RunChatCompletionType.ExplainThis:
            {
                const filename = request.filename || 'Untitled.ipynb';
                return GitHubCopilot.explainThisRequest(
                    request.content,
                    request.language || 'python',
                    filename
                );
            }
        case RunChatCompletionType.FixThis:
            {
                const filename = request.filename || 'Untitled.ipynb';
                return GitHubCopilot.fixThisRequest(
                    request.content,
                    request.language || 'python',
                    filename
                );
            }
        case RunChatCompletionType.NewNotebook:
            {
                return GitHubCopilot.newNotebookRequest(
                    request.content,
                    request.parentDirectory!
                );
            }
    }
}

function SidebarComponent(props: any) {
    const [chatMessages, setChatMessages] = useState<IChatMessage[]>([]);
    const [prompt, setPrompt] = useState<string>('');
    const messagesEndRef = useRef<null | HTMLDivElement>(null);
    const [ghLoginStatus, setGHLoginStatus] = useState(GitHubCopilotLoginStatus.NotLoggedIn);
    const [loginClickCount, setLoginClickCount] = useState(0);
    const [deviceActivationURL, setDeviceActivationURL] = useState('');
    const [deviceActivationCode, setDeviceActivationCode] = useState('');
    const [copilotRequestInProgress, setCopilotRequestInProgress] = useState(false);

    useEffect(() => {
        const fetchData = () => {
            setGHLoginStatus(GitHubCopilot.getLoginStatus());
            const info = GitHubCopilot.getDeviceVerificationInfo();
            if (info.verificationURI && info.userCode) {
                setDeviceActivationURL(info.verificationURI);
                setDeviceActivationCode(info.userCode);
            }
        };

        fetchData();

        const intervalId = setInterval(fetchData, 3000);

        return () => clearInterval(intervalId);
    }, [loginClickCount]);

    const onPromptChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        setPrompt(event.target.value);
    };

    const onPromptKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.shiftKey && event.key == 'Enter') {
            const newList = [
                ...chatMessages,
                {
                    id: UUID.uuid4(),
                    date: new Date(),
                    from: "user",
                    contents: [{
                        type: ResponseStreamDataType.Markdown,
                        content: prompt
                    }],
                }
            ];
            setChatMessages(newList);

            if (prompt.startsWith('/clear')) {
                setChatMessages([]);
                setPrompt('');
                event.stopPropagation();
                event.preventDefault();
                return;
            } else if (prompt.startsWith('/logout')) {
                setChatMessages([]);
                setPrompt('');
                event.stopPropagation();
                event.preventDefault();
                await GitHubCopilot.logoutFromGitHub();
                setLoginClickCount(loginClickCount + 1);
                return;
            }

            setCopilotRequestInProgress(true);
            
            const activeDocInfo: IActiveDocumentInfo = props.getActiveDocumentInfo();
            const newNotebookPrefix = '/newNotebook ';
            const isNewNotebook = prompt.startsWith(newNotebookPrefix);
            const extractedPrompt = isNewNotebook ? prompt.substring(newNotebookPrefix.length) : prompt;
            const serverRoot = activeDocInfo.serverRoot!;
            const parentDirectory = activeDocInfo.parentDirectory!;
            const contents: IChatMessageContent[] = [];

            submitCompletionRequest({
                type: isNewNotebook ? RunChatCompletionType.NewNotebook : RunChatCompletionType.Chat,
                content: extractedPrompt,
                language: activeDocInfo.language,
                filename: activeDocInfo.filename,
                parentDirectory
            }, {
                emit:(response) => {
                    let responseMessage = '';
                    let notebookPath = undefined;
                    if (isNewNotebook) {
                        if (response.data.notebook_path) {
                            notebookPath = response.data.notebook_path;
                            if (notebookPath.startsWith(serverRoot)) {
                                notebookPath = notebookPath.substring(serverRoot.length + 1);
                            }
                            responseMessage = `Notebook saved to **${notebookPath}**`;
                        } else {
                            responseMessage = `Failed to generate notebook. Please try again.`;
                        }
                    } else {
                        if (response.type === 'StreamMessage') {
                            const delta = response.data["choices"]?.[0]?.["delta"];
                            if (!delta) {
                                return;
                            }
                            if (delta["nbiContent"]) {
                                const nbiContent = delta["nbiContent"];
                                contents.push({
                                    type: nbiContent.type,
                                    content: nbiContent.content
                                });
                            } else {
                                responseMessage = response.data["choices"]?.[0]?.["delta"]?.["content"];
                                if (!responseMessage) {
                                    return;
                                }
                                contents.push({
                                    type: ResponseStreamDataType.Markdown,
                                    content: responseMessage
                                });
                            }
                        } else if (response.type === 'StreamEnd') {
                            setCopilotRequestInProgress(false);
                        }
                    }
                    setChatMessages([
                        ...newList,
                        {
                            id: UUID.uuid4(),
                            date: new Date(),
                            from: 'copilot',
                            contents: contents,
                            notebookLink: notebookPath
                        }
                    ]);
                }
            });
            setPrompt('');
            event.stopPropagation();
            event.preventDefault();
        }
    };

    const scrollMessagesToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    };

    const handleLoginClick = async () => {
        const response = await GitHubCopilot.loginToGitHub();
        setDeviceActivationURL((response as any).verificationURI);
        setDeviceActivationCode((response as any).userCode);
        setLoginClickCount(loginClickCount + 1);
    };

    // const handleLogoutClick = () => {
    //     // GitHubCopilot.logoutFromGitHub();
    //     setLoginClickCount(loginClickCount + 1);
    // };
    
    useEffect(() => {
        scrollMessagesToBottom();
    }, [copilotRequestInProgress]);

    const promptRequestHandler = useCallback((eventData: any) => {
        const request: IRunChatCompletionRequest = eventData.detail;
        const message = request.type === RunChatCompletionType.ExplainThis ?
            `Explain this code:\n\`\`\`\n${request.content}\n\`\`\`\n` :
            `Fix this code:\n\`\`\`\n${request.content}\n\`\`\`\n`;
        const newList = [
            ...chatMessages,
            {
                id: UUID.uuid4(),
                date: new Date(),
                from: 'user',
                contents: [{
                    type: ResponseStreamDataType.Markdown,
                    content: message
                }]
            }
        ];
        setChatMessages(newList);

        setCopilotRequestInProgress(true);
        submitCompletionRequest(request, {
            emit: (response) => {
                setChatMessages([
                    ...newList,
                    {
                        id: UUID.uuid4(),
                        date: new Date(),
                        from: 'copilot',
                        contents: [{
                            type: ResponseStreamDataType.Markdown,
                            content: response.data.message
                        }]
                    }
                ]);
                setCopilotRequestInProgress(false);
            }
        });
    }, [chatMessages]);

    useEffect(() => {
        document.addEventListener("copilotSidebar:runPrompt", promptRequestHandler);
    
        return () => {
            document.removeEventListener("copilotSidebar:runPrompt", promptRequestHandler);
        }
    }, [chatMessages]);


    return (
        <div className="sidebar">
            <div className="sidebar-header">
                <div className='sidebar-title'>Copilot Chat</div>
                <div className='sidebar-copilot-status'>
                    {ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice ? 
                    (<div>Activating device...</div>) :
                        ghLoginStatus === GitHubCopilotLoginStatus.LoggingIn ? 
                        (<div>Logging in...</div>) : null
                    }
                </div>
            </div>
            {ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn &&  (
                <div className='sidebar-login-info'>
                    <div>
                    Your GitHub tokens, code and data is directly transferred to GitHub Copilot as needed without storing any copies other than keeping in the process memory.</div>
                    <div>GitHub Copilot requires a subscription and it is free for some users.
                    GitHub Copilot is subject to the <a href="https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features" target="_blank">GitHub Terms for Additional Products and Features</a>.</div>
                    <div>
                        <h3>Privacy and terms</h3>

By using Copilot Chat you agree to <a href="https://docs.github.com/en/copilot/responsible-use-of-github-copilot-features/responsible-use-of-github-copilot-chat-in-your-ide" target='_blank'>GitHub Copilot chat terms</a>. Review the terms to understand about usage, limitations and ways to improve Copilot Chat. Please review <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" target="_blank">Privacy Statement</a> to ensure that your code snippets will not be used as suggested code for other users of GitHub Copilot.</div>
                    <div>Activate this app for access to GitHub Copilot service</div>
                    <div><button onClick={handleLoginClick}>Activate using GitHub account</button></div>
                </div>
            )}
            {
            (ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice && deviceActivationURL && deviceActivationCode) &&
            (<div className='copilot-activation-message'>Please visit <a href={deviceActivationURL} target='_blank'>{deviceActivationURL}</a> and use code <span className="user-code-span" onClick={() => {navigator.clipboard.writeText(deviceActivationCode); return true;}}><b>{deviceActivationCode}&#x1F4CB;</b></span> to allow access to GitHub Copilot from this app.</div>)
            }
            {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn && chatMessages.length == 0 ?
                (
                <div className="sidebar-messages">
                    <div className="sidebar-greeting">
                    Welcome! How can I assist you today?
                    </div>
                </div>
                ) : (
                <div className="sidebar-messages">
                    {chatMessages.map((msg, index) => (
                        <ChatResponse key={`key-${index}`} message={msg} openFile={props.openFile} getApp={props.getApp} />
                    ))}
                    <div className='copilot-progress-row' style={{display: `${copilotRequestInProgress ? 'flex' : 'none'}`}}>
                        <div className='copilot-progress'></div>
                    </div>
                    <div ref={messagesEndRef} />
                </div>
            )}
            {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn &&  (
                <div className="sidebar-footer">
                    <textarea rows={3} onChange={onPromptChange} onKeyDown={onPromptKeyDown} placeholder='Ask Copilot...' value={prompt} />
                </div>
            )}
            
        </div>
      );
}
