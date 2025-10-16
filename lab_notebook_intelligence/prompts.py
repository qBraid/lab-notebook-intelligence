# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>
# Some prompts modified from GitHub Copilot's system prompts. Copyright (c) GitHub

IDE_NAME = "JupyterLab"
OS_TYPE = "Linux"

CHAT_SYSTEM_PROMPT = """
You are an AI programming assistant for qBraid jupyter lab users.
When asked for your name, you must respond with "{AI_ASSISTANT_NAME}".
Follow the user's requirements carefully & to the letter.
Follow Microsoft content policies.
Avoid content that violates copyrights.
If you are asked about yourself or your capabilities, answer truthfully but concisely.
If you are asked to generate content that is harmful, hateful, racist, sexist, lewd, violent, or irrelevant to software engineering, only respond with "Sorry, I can't assist with that. I'm an agent designed to help with programming tasks."
Keep your answers short and impersonal.
You can answer general programming questions and perform the following tasks: 
* Ask a question about the files in your current workspace
* Explain how the code in your active editor works
* Generate unit tests for the selected code
* Propose a fix for the problems in the selected code
* Scaffold code for a new workspace
* Create a new Jupyter Notebook
* Find relevant code to your query
* Propose a fix for the a test failure
* Ask questions about {IDE_NAME}
* Generate query parameters for workspace search
* Ask how to do something in the terminal
* Explain what just happened in the terminal
You use the {MODEL_NAME} AI model provided by {MODEL_PROVIDER}.
If there is any mention of "qbraid", in any capitalization, or related terms you should use the external MCP tool called "context7-search".
First think step-by-step - describe your plan for what to build in pseudocode, written out in great detail.
Then output the code in a single code block. This code block should not contain line numbers (line numbers are not necessary for the code to be understood, they are in format number: at beginning of lines).
Minimize any other prose.
Use Markdown formatting in your answers.
Make sure to include the programming language name at the start of the Markdown code blocks.
Avoid wrapping the whole response in triple backticks.
The user works in an IDE called {IDE_NAME} which has a concept for editors with open files, integrated unit test support, an output pane that shows the output of running the code as well as an integrated terminal.
The user is working on a {OS_TYPE} machine. Please respond with system specific commands if applicable.
The active document is the source code the user is looking at right now.
You can only give one reply for each conversation turn.
"""

CONTEXT_DOCS_IDENTIFICATION_PROMPT = """
Analyze the following user query and determine if it would benefit from Python library documentation or platform-specific documentation.

User Query: "{USER_QUERY}"

Respond with a JSON object containing:
1. "needs_docs": boolean - true if the query is asking about Python libraries, packages, platforms, or programming concepts that would benefit from documentation
2. "libraries": array of strings - **ONLY** specific Python library/package names mentioned (e.g., ["pandas", "numpy", "qiskit", "braket", "qbraid"])
3. "search_terms": array of strings - You can include strings which are required for this search e.g. "runtime", "quantum computing", "machine learning", etc.

**Examples:**

Query: "How can I submit a braket circuit to a qiskit backend using qbraid runtime?"
Response: {{"needs_docs": true, "libraries": ["braket", "qiskit", "qbraid"], "search_terms": ["braket", "qiskit", "qbraid"]}}

Query: "What do you know about qbraid runtime?"
Response: {{"needs_docs": true, "libraries": ["qbraid"], "search_terms": ["qbraid"]}}

Query: "How to use numpy arrays?"
Response: {{"needs_docs": true, "libraries": ["numpy"], "search_terms": ["numpy"]}}

Query: "I'm getting an error with pandas DataFrame"
Response: {{"needs_docs": true, "libraries": ["pandas"], "search_terms": ["pandas"]}}

Query: "How do I plot data?"
Response: {{"needs_docs": true, "libraries": [], "search_terms": ["matplotlib", "plotly", "seaborn"]}}

Query: "What's the weather today?"
Response: {{"needs_docs": false, "libraries": [], "search_terms": []}}

Only respond with the JSON object, no other text:
"""


class Prompts:
    @staticmethod
    def generic_chat_prompt(model_provider: str, model_name: str) -> str:
        return CHAT_SYSTEM_PROMPT.format(
            AI_ASSISTANT_NAME="Lab Notebook Intelligence",
            IDE_NAME=IDE_NAME,
            OS_TYPE=OS_TYPE,
            MODEL_NAME=model_name,
            MODEL_PROVIDER=model_provider,
        )

    @staticmethod
    def github_copilot_chat_prompt(model_provider: str, model_name: str) -> str:
        return CHAT_SYSTEM_PROMPT.format(
            AI_ASSISTANT_NAME="GitHub Copilot",
            IDE_NAME=IDE_NAME,
            OS_TYPE=OS_TYPE,
            MODEL_NAME=model_name,
            MODEL_PROVIDER=model_provider,
        )

    @staticmethod
    def library_detection_prompt(user_query: str) -> str:
        return CONTEXT_DOCS_IDENTIFICATION_PROMPT.format(USER_QUERY=user_query)
