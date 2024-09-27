import React, { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';
import { Signal } from '@lumino/signaling';
import Markdown from 'react-markdown';

import { requestAPI } from './handler';

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
    const data = await requestAPI<any>('chat', { method: 'POST', body: JSON.stringify({"prompt": prompt})});
    return data;
}

function SidebarComponent(props: any) {
    const [chatResponses, setChatResponses] = useState<IChatResponse[]>([]);
    const [prompt, setPrompt] = useState<string>('');
    const messagesEndRef = useRef<null | HTMLDivElement>(null);

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
            Copilot
            </div>
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
