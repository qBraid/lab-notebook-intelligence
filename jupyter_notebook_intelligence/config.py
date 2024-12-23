# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import abc
from dataclasses import dataclass
from enum import Enum
import traitlets
from traitlets.config import Configurable

# from jupyter_notebook_intelligence.agents import AgentManager
# from jupyter_notebook_intelligence.github_copilot import GithubCopilotChatAgent


class ContextType(Enum):
    InlineCompletion = 'inline-completion'
    Completion = 'completion'
    Chat = 'chat'
    NewNotebook = 'new-notebook'

@dataclass
class ContextInputFileInfo:
    file_name: str = ''
    parent_dir: str = ''
    server_root: str = ''

@dataclass
class ContextRequest:
    type: ContextType
    file_info: ContextInputFileInfo = None
    language: str = ''
    prefix: str = ''
    suffix: str = ''

@dataclass
class Context:
    content: str
    file_path: str = None

@dataclass
class ContextResponse:
    items: list[Context]

class ContextProvider(abc.ABC):
    @abc.abstractmethod
    def get_context(self, request: ContextRequest) -> ContextResponse:
        pass

class NotebookIntelligenceConfig(Configurable):
    context_provider_class = traitlets.Type(
        default_value=None,
        klass=ContextProvider,
        allow_none=True,
        config=True,
        help="The context provider class to use."
    )

    def __init__(self, config=None):
        super(NotebookIntelligenceConfig, self).__init__(config=config)

        # default_chat_agent = GithubCopilotChatAgent()
        # self.agent_manager = AgentManager(default_chat_agent)

        self._context_provider = None
        if self.context_provider_class is not None and issubclass(self.context_provider_class, ContextProvider):
            self._context_provider = self.context_provider_class()

    @property
    def has_context_provider(self) -> bool:
        return self.context_provider is not None
    
    @property
    def context_provider(self) -> ContextProvider:
        return self._context_provider
