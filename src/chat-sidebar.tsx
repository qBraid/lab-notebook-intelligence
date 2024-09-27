import React, { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import { Signal } from '@lumino/signaling';
import Markdown from 'react-markdown';

import { GitHubCopilot, GitHubCopilotLoginStatus } from './github-copilot';

export class ChatSidebar extends ReactWidget {
    constructor() {
        super();

        this.node.style.height = '100%';
    }

    render(): JSX.Element {
        return <SidebarComponent promptRequested={this._promptRequested} />;
    }

    runPrompt(prompt: string) {
        this._promptRequested.emit(prompt);
    }

    private _promptRequested = new Signal<this, string>(this);
}

interface IChatResponse {
    message: string;
}

function ChatResponse(props: any) {
    return (
        <div className="chat-response">
            <Markdown>{props.message}</Markdown>
        </div>
    );
}

async function submitChatRequest(prompt: string): Promise<any> {
    const data = await GitHubCopilot.chatRequest(prompt);
    return data;
}

function SidebarComponent(props: any) {
    const [chatResponses, setChatResponses] = useState<IChatResponse[]>([]);
    const [prompt, setPrompt] = useState<string>('');
    const messagesEndRef = useRef<null | HTMLDivElement>(null);
    const [ghLoginStatus, setGHLoginStatus] = useState(GitHubCopilotLoginStatus.NotLoggedIn);
    const [loginClickCount, setLoginClickCount] = useState(0);
    const [deviceActivationURL, setDeviceActivationURL] = useState('');
    const [deviceActivationCode, setDeviceActivationCode] = useState('');

    useEffect(() => {
        const fetchData = () => {
            setGHLoginStatus(GitHubCopilot.getLoginStatus());
        };

        fetchData();

        const intervalId = setInterval(fetchData, 3000);

        return () => clearInterval(intervalId);
    }, [loginClickCount]);

    const promptRequestHandler = (_sender: any, prompt:string) => {
        submitChatRequest(prompt).then((response) => {
            setChatResponses([...chatResponses, {message: response.data.message}]);
        });
    };

    const onPromptChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        setPrompt(event.target.value);
    };

    const onPromptKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.shiftKey && event.key == 'Enter') {
            submitChatRequest(prompt).then((response) => {
                setChatResponses([...chatResponses, {message: response.data.message}]);
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

    const handleLogoutClick = () => {
        // GitHubCopilot.logoutFromGitHub();
        setLoginClickCount(loginClickCount + 1);
    };
    
    useEffect(() => {
        scrollMessagesToBottom();
    }, [chatResponses]);

    useEffect(() => {
        props.promptRequested.disconnect(promptRequestHandler);
        props.promptRequested.connect(promptRequestHandler);
    }, []);


    return (
        <div className="sidebar">
            <div className="sidebar-header">
                <div className='sidebar-title'>Copilot</div>
                <div>
                    {ghLoginStatus === GitHubCopilotLoginStatus.NotLoggedIn ? 
                        (<button onClick={handleLoginClick}>Login</button>) :
                    ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice ? 
                    (<div>Activating device...</div>) :
                        ghLoginStatus === GitHubCopilotLoginStatus.LoggingIn ? 
                        (<div>Logging in...</div>) :(<button onClick={handleLogoutClick}>Logout</button>)
                    }
                </div>
            </div>
            {
            ghLoginStatus === GitHubCopilotLoginStatus.ActivatingDevice && 
            (<div>Please visit <a href="{deviceActivationURL}" target='_blank'>{deviceActivationURL}</a> and use code <b>{deviceActivationCode}</b> to allow access from this device.</div>)
            }
            <div className="sidebar-messages">
                {chatResponses.map((chatResponse, index) => (
                    <ChatResponse key={`key-${index}`} message={chatResponse.message} />
                ))}
                <div ref={messagesEndRef} />
            </div>
            <div className="sidebar-footer">
                <textarea rows={2} onChange={onPromptChange} onKeyDown={onPromptKeyDown} placeholder='Ask Copilot...' value={prompt} />
            </div>
        </div>
      );
}
