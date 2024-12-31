from time import sleep
from .extension import AnchorData, ButtonData, ChatCommand, HTMLData, MarkdownData, NotebookIntelligenceExtension, Host, ChatParticipant, ChatRequest, ChatResponse, ProgressData, ResponseStreamDataType, Tool, ToolPreInvokeResponse

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
    
    @property
    def tools(self) -> list[Tool]:
        return [ConvertFahrenheitToCelciusTool(), ConvertCelciusToKelvinTool()]

    async def handle_chat_request(self, request: ChatRequest, response: ChatResponse) -> None:
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

        await self.handle_chat_request_with_tools(request, response)
        

class ConvertFahrenheitToCelciusTool(Tool):
    @property
    def name(self) -> str:
        return "convert_fahnrenheit_to_celcius"

    @property
    def title(self) -> str:
        return "Convert Fahrenheit to Celcius Tool"
    
    @property
    def tags(self) -> list[str]:
        return ["test-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that converts fahrenheit to celcius"
    
    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "temperature": {
                            "type": "number",
                            "description": "Temperature in fahrenheit",
                        }
                    },
                    "required": ["temperature"],
                    "additionalProperties": False,
                },
            },
        }

    def pre_invoke(self, request: ChatRequest, tool_args: dict) -> ToolPreInvokeResponse | None:
        return ToolPreInvokeResponse(
            message="Converting fahrenheit to celcius",
            confirmationTitle="Confirm conversion",
            confirmationMessage="Are you sure you want to convert the temperature?"
        )

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        temperature = tool_args.get('temperature')
        return {"celcius": (temperature - 32) * 5/9}

class ConvertCelciusToKelvinTool(Tool):
    @property
    def name(self) -> str:
        return "convert_celcius_to_kelvin"

    @property
    def title(self) -> str:
        return "Convert Celcius to Kelvin Tool"
    
    @property
    def tags(self) -> list[str]:
        return ["test-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that converts celcius to kelvin"
    
    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "temperature": {
                            "type": "number",
                            "description": "Temperature in celcius",
                        }
                    },
                    "required": ["temperature"],
                    "additionalProperties": False,
                },
            },
        }

    def pre_invoke(self, request: ChatRequest, tool_args: dict) -> ToolPreInvokeResponse | None:
        return ToolPreInvokeResponse(
            message="Converting celcius to kelvin",
            # confirmationTitle="Confirm",
            # confirmationMessage="Are you sure you want to convert the temperature?"
        )

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        temperature = tool_args.get('temperature')
        return {"kelvin": temperature + 273.15}

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
        self.tool = ConvertFahrenheitToCelciusTool()
        self.inline_completion_context_provider = TestInlineCompletionContextProvider()

    @property
    def id(self) -> str:
        return "test-extension"

    @property
    def name(self) -> str:
        return "Test Extension"

    def activate(self, host: Host) -> None:
        host.register_chat_participant(self.participant)
        host.register_inline_completion_context_provider(self.inline_completion_context_provider)
