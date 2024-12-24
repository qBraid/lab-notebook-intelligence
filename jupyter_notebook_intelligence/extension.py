# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
from os import path
import os
import sys
from typing import Dict
from dataclasses import dataclass

DEFAULT_CHAT_AGENT_ID = 'default'

@dataclass
class ChatRequest:
    host: 'Host' = None
    command: str = ''
    prompt: str = ''

class ChatResponse:
    def stream(self, data) -> None:
        raise NotImplemented

@dataclass
class ToolResponse:
    response: str = ''

class ChatParticipant:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def description(self) -> str:
        raise NotImplemented
    
    @property
    def commands(self) -> list[str]:
        raise NotImplemented

    def handle_chat_request(self, request: ChatRequest, response: ChatResponse) -> None:
        raise NotImplemented
    
class Tool:
    @property
    def id(self) -> str:
        raise NotImplemented

    def handle_tool_call(self, request: ChatRequest) -> ToolResponse:
        raise NotImplemented

class InlineCompletionContextProvider:
    @property
    def id(self) -> str:
        raise NotImplemented

    def handle_completion_context_request(self, request: ChatRequest, response: ChatResponse) -> None:
        raise NotImplemented

class Host:
    def register_chat_participant(self, participant: ChatParticipant) -> None:
        raise NotImplemented
    
    def register_tool(self, tool: Tool) -> None:
        raise NotImplemented
    
    def register_inline_completion_context_provider(self, provider: InlineCompletionContextProvider) -> None:
        raise NotImplemented


class NotebookIntelligenceExtension:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def chat_agents(self) -> list[ChatParticipant]:
        raise NotImplemented

    def activate(self, host: Host) -> None:
        raise NotImplemented

class ExtensionManager(Host):
    def __init__(self, default_chat_participant: ChatParticipant):
        self.chat_participants: Dict[str, ChatParticipant] = {}
        self.default_chat_participant = default_chat_participant
        self.initialize()

    def initialize(self):
        self.chat_participants = {}
        self.register_chat_participant(self.default_chat_participant)

    def initialize_extensions(self):
        extensions_dir = path.join(sys.prefix, "share", "jupyter", "nbiextensions")
        if not path.exists(extensions_dir):
            return
        subfolders = [f.path for f in os.scandir(extensions_dir) if f.is_dir()]
        for extension_dir in list(subfolders):
            metadata_path = path.join(extension_dir, "extension.json")
            if path.exists(metadata_path) and path.isfile(metadata_path):
                with open(metadata_path, 'r') as file:
                    data = json.load(file)
                    class_name = data['class']
                    extension = self.load_extension(class_name)
                    if extension:
                        extension.activate(self)
    
    def load_extension(extension_class: str) -> NotebookIntelligenceExtension:
        import importlib
        try:
            parts = extension_class.split(".")
            module_name = ".".join(parts[0:-1])
            class_name = parts[-1]
            ExtensionClass = getattr(importlib.import_module(module_name), class_name)
            if ExtensionClass is not None and issubclass(ExtensionClass, NotebookIntelligenceExtension):
                instance = ExtensionClass()
                return instance
        except:
            pass

        return None
    
    def register_chat_participant(self, participant: ChatParticipant):
        self.chat_participants[participant.id] = participant

    def register_tool(self, tool: Tool) -> None:
        pass
    
    def register_inline_completion_context_provider(self, provider: InlineCompletionContextProvider) -> None:
        pass

    def get_chat_participant_id(self, request: ChatRequest) -> str:
        prompt = request.prompt.lstrip()
        if prompt.startswith('@'):
            try:
                space_loc = prompt.index(' ')
                id = prompt[1: space_loc]
                if id in self.chat_participants:
                    return id
            except:
                pass
        
        return DEFAULT_CHAT_AGENT_ID

    def get_chat_participant(self, request: ChatRequest) -> ChatParticipant:
        agent_id = self.get_chat_participant_id(request)
        return self.chat_participants[agent_id]

    def handle_chat_request(self, request: ChatRequest) -> None:
        request.host = self
        agent = self.get_chat_participant(request)
        return agent.handle_chat_request(request, self)
