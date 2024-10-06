// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { ChangeEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import Markdown from 'react-markdown';
import { UUID } from '@lumino/coreutils';

import { GitHubCopilot, GitHubCopilotLoginStatus } from './github-copilot';
import { IActiveDocumentInfo } from './tokens';

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
}

export class ChatSidebar extends ReactWidget {
    constructor(options: IChatSidebarOptions) {
        super();

        this.node.style.height = '100%';
        this._getActiveDocumentInfo = options.getActiveDocumentInfo;
        this._openFile = options.openFile;
    }

    render(): JSX.Element {
        return <SidebarComponent getActiveDocumentInfo={this._getActiveDocumentInfo} openFile={this._openFile} />;
    }

    private _getActiveDocumentInfo: () => IActiveDocumentInfo;
    private _openFile: (path: string) => void;
}

interface IChatMessage {
    id: string;
    parentId?: string;
    date: Date;
    from: string; // 'user' | 'copilot';
    message: string;
    notebookLink?: string;
}

function ChatResponse(props: any) {
    const msg: IChatMessage = props.message;
    const timestamp = `${msg.date.getHours()}:${msg.date.getMinutes()}:${msg.date.getSeconds()}`;

    const openNotebook = (event: any) => {
        const notebookPath = event.target.dataset['ref'];
        props.openFile(notebookPath);
    };

    return (
        <div className={`chat-message chat-message-${msg.from}`} >
            <div className="chat-message-header">
                <div className="chat-message-from">{msg.from === 'user' ? 'User' : 'Copilot'}</div>
                <div className="chat-message-timestamp">{timestamp}</div>
            </div>
            <div className="chat-message-content">
                <Markdown>{msg.message}</Markdown>
                {msg.notebookLink && (
                    <a className="copilot-generated-notebook-link" data-ref={msg.notebookLink} onClick={openNotebook}>open notebook</a>
                )}
            </div>
        </div>
    );
}

async function submitCompletionRequest(request: IRunChatCompletionRequest): Promise<any> {
    switch (request.type) {
        case RunChatCompletionType.Chat:
            return GitHubCopilot.chatRequest(
                request.content,
                request.language || 'python',
                request.filename || 'Untitled.ipynb'
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
                    message: prompt
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

            submitCompletionRequest({
                type: isNewNotebook ? RunChatCompletionType.NewNotebook : RunChatCompletionType.Chat,
                content: extractedPrompt,
                language: activeDocInfo.language,
                filename: activeDocInfo.filename,
                parentDirectory
            }).then((response) => {
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
                    responseMessage = response.data.message;
                }
                setChatMessages([
                    ...newList,
                    {
                        id: UUID.uuid4(),
                        date: new Date(),
                        from: 'copilot',
                        message: responseMessage,
                        notebookLink: notebookPath
                    }
                ]);
                setCopilotRequestInProgress(false);
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
            `Explain this code:\n\`\`\`\n${request.content}\`\`\`\n` :
            `Fix this code:\n\`\`\`\n${request.content}\`\`\`\n`;
        const newList = [
            ...chatMessages,
            {
                id: UUID.uuid4(),
                date: new Date(),
                from: 'user',
                message
            }
        ];
        setChatMessages(newList);

        setCopilotRequestInProgress(true);
        submitCompletionRequest(request).then((response) => {
            setChatMessages([
                ...newList,
                {
                    id: UUID.uuid4(),
                    date: new Date(),
                    from: 'copilot',
                    message: response.data.message
                }
            ]);
            setCopilotRequestInProgress(false);
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
                <div className='sidebar-title'>Copilot</div>
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
                        <ChatResponse key={`key-${index}`} message={msg} openFile={props.openFile} />
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
