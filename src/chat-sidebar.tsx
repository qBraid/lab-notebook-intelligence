// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { ChangeEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import Markdown from 'react-markdown';
import { UUID } from '@lumino/coreutils';

import { GitHubCopilot, GitHubCopilotLoginStatus } from './github-copilot';

export enum RunChatCompletionType {
    Chat,
    ExplainThis,
    FixThis,
}

export interface IRunChatCompletionRequest {
    type: RunChatCompletionType,
    content: string
}

export class ChatSidebar extends ReactWidget {
    constructor() {
        super();

        this.node.style.height = '100%';
    }

    render(): JSX.Element {
        return <SidebarComponent />;
    }
}

interface IChatMessage {
    id: string;
    parentId?: string;
    date: Date;
    from: string; // 'user' | 'copilot';
    message: string;
}

function ChatResponse(props: any) {
    const msg: IChatMessage = props.message;
    const timestamp = `${msg.date.getHours()}:${msg.date.getMinutes()}:${msg.date.getSeconds()}`;

    return (
        <div className={`chat-message chat-message-${msg.from}`} >
            <div className="chat-message-header">
                <div className="chat-message-from">{msg.from === 'user' ? 'User' : 'Copilot'}</div>
                <div className="chat-message-timestamp">{timestamp}</div>
            </div>
            <div className="chat-message-content">
                <Markdown>{msg.message}</Markdown>
            </div>
        </div>
    );
}

async function submitCompletionRequest(request: IRunChatCompletionRequest): Promise<any> {
    switch (request.type) {
        case RunChatCompletionType.Chat:
            return GitHubCopilot.chatRequest(request.content);
        case RunChatCompletionType.ExplainThis:
            {
                const content = `Active file is main.py. Can you explain this code:\n${request.content}`;
                return GitHubCopilot.explainThisRequest(content);
            }
        case RunChatCompletionType.FixThis:
            {
                const content = `Active file is a Jupyter notebook named main.ipynb. Can you fix this code:\n${request.content}`;
                return GitHubCopilot.fixThisRequest(content);
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

    const onPromptKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
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

            setCopilotRequestInProgress(true);
            submitCompletionRequest({type: RunChatCompletionType.Chat, content: prompt}).then((response) => {
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
                    {ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn ? 
                        (<button onClick={handleLoginClick}>Login</button>) :
                    ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice ? 
                    (<div>Activating device...</div>) :
                        ghLoginStatus === GitHubCopilotLoginStatus.LoggingIn ? 
                        (<div>Logging in...</div>) : null
                    }
                </div>
            </div>
            {
            (ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice && deviceActivationURL && deviceActivationCode) &&
            (<div className='copilot-activation-message'>Please visit <a href={deviceActivationURL} target='_blank'>{deviceActivationURL}</a> and use code <b>{deviceActivationCode}</b> to allow access from this device.</div>)
            }
            {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn &&  (
                <div className="sidebar-messages">
                    {chatMessages.map((msg, index) => (
                        <ChatResponse key={`key-${index}`} message={msg} />
                    ))}
                    <div className='copilot-progress-row' style={{display: `${copilotRequestInProgress ? 'flex' : 'none'}`}}>
                        <div className='copilot-progress'></div>
                    </div>
                    <div ref={messagesEndRef} />
                </div>
            )}
            {ghLoginStatus === GitHubCopilotLoginStatus.LoggedIn &&  (
                <div className="sidebar-footer">
                    <textarea rows={2} onChange={onPromptChange} onKeyDown={onPromptKeyDown} placeholder='Ask Copilot...' value={prompt} />
                </div>
            )}
            
        </div>
      );
}
