import React, { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import { ReactWidget } from '@jupyterlab/apputils';

import { requestAPI } from './handler';

export class ChatSidebar extends ReactWidget {
    constructor() {
        super();

        this.node.style.height = '100%';
    }

    render(): JSX.Element {
        return <SidebarComponent />;
    }
}

interface IChatResponse {
    message: string;
}

function ChatResponse(props: any) {
    return (
        <div className="chat-response">{props.message}</div>
    );
}

async function submitChatRequest(prompt: string): Promise<any> {
    const data = await requestAPI<any>('chat', { method: 'POST', body: JSON.stringify({"prompt": prompt})});
    return data;
}

function SidebarComponent(props: any) {
    const [chatResponses, setChatResponses] = useState<IChatResponse[]>([]);
    const [prompt, setPrompt] = useState<string>('');
    const messagesEndRef = useRef<null | HTMLDivElement>(null)

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
      }
    
      useEffect(() => {
        scrollMessagesToBottom()
      }, [chatResponses]);

    return (
        <div className="sidebar">
            <div className="sidebar-header">
            Notebook Intelligence
            </div>
            <div className="sidebar-messages">
                {chatResponses.map((chatResponse, index) => (
                    <ChatResponse key={`key-${index}`} message={chatResponse.message} />
                ))}
                <div ref={messagesEndRef} />
            </div>
            <div className="sidebar-footer">
                <textarea rows={2} onChange={onPromptChange} onKeyDown={onPromptKeyDown} placeholder='Enter your messages...' value={prompt} />
            </div>
        </div>
      );
}
