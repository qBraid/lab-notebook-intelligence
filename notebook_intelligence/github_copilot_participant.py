# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from notebook_intelligence.api import ChatCommand, ChatParticipant, ChatRequest, ChatResponse, MarkdownData, Tool
from notebook_intelligence.github_copilot import completions
from notebook_intelligence.github_copilot_prompts import CopilotPrompts


class AddMarkdownCellToNotebookTool(Tool):
    @property
    def name(self) -> str:
        return "add_markdown_cell_to_notebook"

    @property
    def title(self) -> str:
        return "Add markdown cell to notebook"
    
    @property
    def tags(self) -> list[str]:
        return ["default-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that adds markdown cell to a notebook"
    
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
                        "markdown_cell_source": {
                            "type": "string",
                            "description": "Markdown to add to the notebook",
                        }
                    },
                    "required": ["markdown_cell_source"],
                    "additionalProperties": False,
                },
            },
        }

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        markdown = tool_args.get('markdown_cell_source')
        ui_cmd_response = await response.run_ui_command('notebook-intelligence:add-markdown-cell-to-notebook', {'markdown': markdown, 'path': tool_context.get('file_path')})
        return {}

class AddCodeCellTool(Tool):
    @property
    def name(self) -> str:
        return "add_code_cell_to_notebook"

    @property
    def title(self) -> str:
        return "Add code cell to notebook"
    
    @property
    def tags(self) -> list[str]:
        return ["default-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that adds code cell to a notebook"
    
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
                        "code_cell_source": {
                            "type": "string",
                            "description": "Code to add to the notebook",
                        }
                    },
                    "required": ["code_cell_source"],
                    "additionalProperties": False,
                },
            },
        }

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        code = tool_args.get('code_cell_source')
        ui_cmd_response = await response.run_ui_command('notebook-intelligence:add-code-cell-to-notebook', {'code': code, 'path': tool_context.get('file_path')})
        return {}

class GithubCopilotChatParticipant(ChatParticipant):
    @property
    def id(self) -> str:
        return "default"
    
    @property
    def commands(self) -> list[ChatCommand]:
        return [
            ChatCommand(name='newNotebook', description='Create a new notebook'),
            ChatCommand(name='newPythonFile', description='Create a new Python file'),
            ChatCommand(name='clear', description='Clears chat history'),
        ]

    @property
    def tools(self) -> list[Tool]:
        return [AddMarkdownCellToNotebookTool(), AddCodeCellTool()]

    @property
    def allowed_context_providers(self) -> set[str]:
        # any context provider can be used
        return set(["*"])

    async def handle_chat_request(self, request: ChatRequest, response: ChatResponse, options: dict = {}) -> None:
        if request.command == 'newNotebook':
            # create a new notebook
            ui_cmd_response = await response.run_ui_command('notebook-intelligence:create-new-notebook-from-py', {'code': ''})
            file_path = ui_cmd_response['path']
            tool_names = [tool.name for tool in self.tools]
            request.chat_history.insert(0, {"role": "system", "content": f"You are an assistant that creates Jupyter notebooks. Use the functions provided to add markdown or code cells to the notebook. Code cells are written in Python. Markdown cells are written in Markdown. Call the functions with either Python or Markdown content. Do not repeat the code in the code cells with markdown explanations. You have only two functions available to you: '{tool_names[0]}' and '{tool_names[1]}'. Do not assume the availibility of any other tools or functions. Make sure to generate at least one code cell and one markdown cell."})
            await self.handle_chat_request_with_tools(request, response, options, tool_context={
                'file_path': file_path
            }, tool_choice='required')
            return
        elif request.command == 'newPythonFile':
            # create a new notebook
            messages = [
                {"role": "system", "content": f"You are an assistant that creates Python code. You should return the code directly without any explantion. You should not print message to explain the code or purpose of the code. You should return the code directly, without wrapping it inside ```."},
                {"role": "user", "content": f"Generate code for: {request.prompt}"}
            ]
            generated = completions(messages)
            code = generated['choices'][0]['message']['content']
            ui_cmd_response = await response.run_ui_command('notebook-intelligence:create-new-file', {'code': code })
            file_path = ui_cmd_response['path']
            response.stream(MarkdownData(f"File '{file_path}' created successfully"))
            response.finish()
            return

        messages = [
            {"role": "system", "content": options.get("system_prompt", CopilotPrompts.chat_prompt())},
        ] + request.chat_history

        completions(messages, response=response, cancel_token=request.cancel_token)
