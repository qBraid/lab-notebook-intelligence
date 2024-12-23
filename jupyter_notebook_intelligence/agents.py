# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Dict
from dataclasses import dataclass

DEFAULT_CHAT_AGENT_ID = 'default'

@dataclass
class ChatRequest:
    prompt: str = ''

class NotebookIntelligenceChatAgent:
    @property
    def id(self) -> str:
        raise NotImplemented

    def handle_request(self, request: ChatRequest, agent_manager: 'AgentManager') -> None:
        raise NotImplemented

class NotebookIntelligenceExtension:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def chat_agents(self) -> list[NotebookIntelligenceChatAgent]:
        raise NotImplemented

class AgentManager:
    def __init__(self, default_chat_agent: NotebookIntelligenceChatAgent):
        self.chat_agents: Dict[str, NotebookIntelligenceChatAgent] = {}
        self.default_chat_agent = default_chat_agent
        self.initialize()

    def initialize(self):
        self.chat_agents = {}
        self.register_chat_agent(self.default_chat_agent)

    def register_chat_agent(self, agent: NotebookIntelligenceChatAgent):
        self.chat_agents[agent.id] = agent

    def get_chat_agent_id(self, request: ChatRequest) -> str:
        prompt = request.prompt.lstrip()
        if prompt.startswith('@'):
            try:
                space_loc = prompt.index(' ')
                id = prompt[1: space_loc]
                if id in self.chat_agents:
                    return id
            except:
                pass
        
        return DEFAULT_CHAT_AGENT_ID

    def get_chat_agent(self, request: ChatRequest) -> NotebookIntelligenceChatAgent:
        agent_id = self.get_chat_agent_id(request)
        return self.chat_agents[agent_id]

    def handle_chat_request(self, request: ChatRequest) -> None:
        agent = self.get_chat_agent(request)
        return agent.handle_request(request, self)
