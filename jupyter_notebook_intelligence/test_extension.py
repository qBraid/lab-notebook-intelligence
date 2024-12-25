from time import sleep
from .extension import AnchorData, ButtonData, ChatCommand, HTMLData, MarkdownData, NotebookIntelligenceExtension, Host, ChatParticipant, ChatRequest, ChatResponse, ProgressData, ResponseStreamDataType, Tool, ToolResponse

class TestChatParticipant(ChatParticipant):
    @property
    def id(self) -> str:
        return "test"

    @property
    def name(self) -> str:
        return "Test Participant"

    @property
    def commands(self) -> list[ChatCommand]:
        return [
            ChatCommand(name='repeat', description='Repeats the prompt'),
            ChatCommand(name='test', description='Test command')
        ]

    def handle_chat_request(self, request: ChatRequest, response: ChatResponse) -> None:
        if (request.command == 'repeat'):
            response.stream(MarkdownData(f"repeating: {request.prompt}"))
            response.finish()
            return
        elif (request.command == 'test'):
            for i in range(5):
                response.stream(MarkdownData(f"Hello world {i + 1}!\n\n"))
                sleep(0.2)
            response.stream(ProgressData("Running..."))
            sleep(2)
            response.stream(HTMLData("<b>Bold text</b>"))
            response.stream(AnchorData("https://www.jupyter.org", "Click me!"))
            response.stream(ButtonData("Button title", "apputils:notify", {
                    "message": 'Copilot chat button was clicked',
                    "type": 'success',
                    "options": { "autoClose": False }
            }))
            response.finish()
            return

        self.handle_chat_with_tools(request, response)
        

class TestTool(Tool):
    @property
    def id(self) -> str:
        return "test-tool"

    def handle_tool_call(self, request: ChatRequest) -> ToolResponse:
        return ToolResponse("Hello from tool!")

class TestInlineCompletionContextProvider:
    @property
    def id(self) -> str:
        return "test-inline-completion-context-provider"

    def handle_completion_context_request(self, request: ChatRequest, response: ChatResponse) -> None:
        response.stream(MarkdownData("Hello from inline completion context provider!"))
        response.finish()

class TestExtension(NotebookIntelligenceExtension):
    def __init__(self):
        self.participant = TestChatParticipant()
        self.tool = TestTool()
        self.inline_completion_context_provider = TestInlineCompletionContextProvider()

    @property
    def id(self) -> str:
        return "test-extension"

    @property
    def name(self) -> str:
        return "Test Extension"

    def activate(self, host: Host) -> None:
        host.register_chat_participant(self.participant)
        host.register_tool(self.tool)
        host.register_inline_completion_context_provider(self.inline_completion_context_provider)
