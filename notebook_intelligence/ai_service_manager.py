# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
from os import path
import os
import sys
from typing import Dict
import logging
from notebook_intelligence.api import AIModel, CancelToken, ChatParticipant, ChatRequest, ChatResponse, CompletionContext, ContextRequest, Host, CompletionContextProvider, NotebookIntelligenceExtension, Tool
from notebook_intelligence.github_copilot import completions

log = logging.getLogger(__name__)

DEFAULT_CHAT_PARTICIPANT_ID = 'default'
RESERVED_PARTICIPANT_IDS = set([
    'chat', 'copilot', 'jupyter', 'jupyterlab', 'jlab', 'notebook', 'intelligence', 'nb', 'nbi', 'terminal', 'vscode', 'workspace', 'help', 'ai', 'config', 'settings', 'ui', 'cell', 'code', 'file', 'data', 'new', 'run', 'search'
])

class GitHubAIModel(AIModel):
    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> None:
        return completions(messages, tools, response, cancel_token, options)

class AIServiceManager(Host):
    def __init__(self, default_chat_participant: ChatParticipant):
        self.chat_participants: Dict[str, ChatParticipant] = {}
        self.completion_context_providers: Dict[str, CompletionContextProvider] = {}
        self._default_chat_participant = default_chat_participant
        self.initialize()

    def initialize(self):
        self.chat_participants = {}
        self.register_chat_participant(self._default_chat_participant)
        self.initialize_extensions()

    def initialize_extensions(self):
        extensions_dir = path.join(sys.prefix, "share", "jupyter", "nbi_extensions")
        if not path.exists(extensions_dir):
            return
        subfolders = [f.path for f in os.scandir(extensions_dir) if f.is_dir()]
        for extension_dir in list(subfolders):
            try:
                log.info(f"Loading NBI extension from '{extension_dir}'...")
                metadata_path = path.join(extension_dir, "extension.json")
                if path.exists(metadata_path) and path.isfile(metadata_path):
                    with open(metadata_path, 'r') as file:
                        data = json.load(file)
                        class_name = data['class']
                        extension = self.load_extension(class_name)
                        if extension:
                            extension.activate(self)
                            log.info(f"Activated NBI extension '{class_name}'.")
            except Exception as e:
                log.error(f"Failed to load NBI extension from '{extension_dir}'!\n{e}")
    
    def load_extension(self, extension_class: str) -> NotebookIntelligenceExtension:
        import importlib
        try:
            parts = extension_class.split(".")
            module_name = ".".join(parts[0:-1])
            class_name = parts[-1]
            ExtensionClass = getattr(importlib.import_module(module_name), class_name)
            if ExtensionClass is not None and issubclass(ExtensionClass, NotebookIntelligenceExtension):
                instance = ExtensionClass()
                return instance
        except Exception as e:
            log.error(f"Failed to load NBI extension: '{extension_class}'!\n{e}")

        return None

    def register_chat_participant(self, participant: ChatParticipant):
        if participant.id in RESERVED_PARTICIPANT_IDS:
            log.error(f"Participant ID '{participant.id}' is reserved!")
            return
        if participant.id in self.chat_participants:
            log.error(f"Participant ID '{participant.id}' is already in use!")
            return
        self.chat_participants[participant.id] = participant

    def register_completion_context_provider(self, provider: CompletionContextProvider) -> None:
        if provider.id in self.completion_context_providers:
            log.error(f"Completion Context Provider ID '{provider.id}' is already in use!")
            return
        self.completion_context_providers[provider.id] = provider

    @property
    def default_chat_participant(self) -> ChatParticipant:
        return self._default_chat_participant

    @property
    def model(self) -> AIModel:
        return GitHubAIModel()

    @staticmethod
    def parse_prompt(prompt: str) -> tuple[str, str, str]:
        participant = DEFAULT_CHAT_PARTICIPANT_ID
        command = ''
        input = ''

        prompt = prompt.lstrip()
        parts = prompt.split(' ')
        parts = [part for part in parts if part.strip() != '']

        if len(parts) > 0:
            if parts[0].startswith('@'):
                participant = parts[0][1:]
                parts = parts[1:]

        if len(parts) > 0:
            if parts[0].startswith('/'):
                command = parts[0][1:]
                parts = parts[1:]

        if len(parts) > 0:
            input = " ".join(parts)

        return [participant, command, input]
    
    def get_chat_participant(self, prompt: str) -> ChatParticipant:
        (participant_id, command, input) = AIServiceManager.parse_prompt(prompt)
        return self.chat_participants.get(participant_id, DEFAULT_CHAT_PARTICIPANT_ID)

    async def handle_chat_request(self, request: ChatRequest, response: ChatResponse, options: dict = {}) -> None:
        request.host = self
        (participant_id, command, prompt) = AIServiceManager.parse_prompt(request.prompt)
        participant = self.chat_participants.get(participant_id, DEFAULT_CHAT_PARTICIPANT_ID)
        request.command = command
        request.prompt = prompt
        response.participant_id  = participant_id
        return await participant.handle_chat_request(request, response, options)

    async def get_completion_context(self, request: ContextRequest) -> CompletionContext:
        cancel_token = request.cancel_token
        context = CompletionContext([])

        allowed_context_providers = request.participant.allowed_context_providers

        if cancel_token.is_cancel_requested:
            return context

        for provider in self.completion_context_providers:
            if cancel_token.is_cancel_requested:
                return context
            provider = self.completion_context_providers.get(provider)
            if provider.id not in allowed_context_providers and '*' not in allowed_context_providers:
                continue
            try:
                provider_context = provider.handle_completion_context_request(request)
                if provider_context.items:
                    context.items += provider_context.items
            except Exception as e:
                log.error(f"Error while getting completion context from provider '{provider.id}'!\n{e}")

        return context
