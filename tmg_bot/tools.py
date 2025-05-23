import manim
import random
import sympy
import pathlib
import math
import numpy as np
from typing import Any
from io import StringIO
import json
import time
from .instructions import MANIM_BUILDER_INSTRUCTIONS, MATH_SOLVE_INSTRUCTIONS, BING_SEARCH_INSTRUCTIONS
import discord
import manimpango
import inspect
import os
from .client import project_client, client
from azure.ai.projects.models import BingGroundingTool, MessageRole
from .supabase_client import supabase

bing_connection = project_client.connections.get(connection_name=os.getenv("AZURE_BING_CONNECTION_NAME"))
conn_id = bing_connection.id

print(conn_id)

bing = BingGroundingTool(connection_id=conn_id)

manim.config.tex_template = manim.TexTemplate(
    preamble=r"""
\usepackage[spanish]{babel}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{xcolor}
\usepackage{mlmodern}
"""
)
manim.config.background_color = "#161616"
manim.config.disable_caching = True


def bing_search(
    query: str,
) -> str:
    """Search the internet for information related to the user's query."""
    try:
        agent = project_client.agents.create_agent(
            model="gpt-4o",
            instructions=BING_SEARCH_INSTRUCTIONS,
            name="bing_search",
            tools=bing.definitions,
            headers={"x-ms-enable-preview": "true"},
        )
        thread = project_client.agents.create_thread()
        message = project_client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=query,
        )
        run = project_client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent.id)
        print(f"Run finished with status: {run.status}")
        # Retrieve run step details to get Bing Search query link
        # To render the webpage, we recommend you replace the endpoint of Bing search query URLs with `www.bing.com` and your Bing search query URL would look like "https://www.bing.com/search?q={search query}"
        run_steps = project_client.agents.list_run_steps(run_id=run.id, thread_id=thread.id)
        run_steps_data = run_steps['data']
        print(f"Last run step detail: {run_steps_data}")

        if run.status == "failed":
            print(f"Run failed: {run.last_error}")

        project_client.agents.delete_agent(agent.id)
        print("Deleted agent")

        response_message = project_client.agents.list_messages(thread_id=thread.id).get_last_message_by_role(
            MessageRole.AGENT
        )
        if response_message:
            data = {"text_messages": [], "url_citation_annotations": []}
            for text_message in response_message.text_messages:
                print(f"Agent response: {text_message.text.value}")
                data["text_messages"].append(text_message.text.value)
            for annotation in response_message.url_citation_annotations:
                print(f"URL Citation: [{annotation.url_citation.title}]({annotation.url_citation.url})")
                data["url_citation_annotations"].append(f"[{annotation.url_citation.title}]({annotation.url_citation.url})")
            print("Agent response:", data)
            return str(data)
        else:
            print("No response message found.")
            return "No response message found."
    except Exception as e:
        print(f"Error searching the internet: {e}")
        return "An error occurred while searching the internet. Please try again."


class ResponseScene(manim.Scene):
    _internal_manim_builder_previous_response_id: str | None = None
    _internal_prompt_count: int = 0
    _internal_prompt_limit: int = 500
    _internal_tools: list = [
        {
            "type": "function",
            "name": "exec_python",
            "description": "Executes Python code. Use this to run Manim code inside the `construct` method.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "scope",
            "description": "Returns the current scope variables and functions.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "dir",
            "description": "Lists the available attributes and methods of an object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Python object to list the attributes and methods. Must be available considering the current scope.",
                    },
                },
                "additionalProperties": False,
                "required": ["object"],
            }
        },
        {
            "type": "function",
            "name": "doc",
            "description": "Returns the docstring of a method or attribute.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Python object to get the docstring. Must be available considering the current scope.",
                    },
                },
                "additionalProperties": False,
                "required": ["object"],
            }
        },
        {
            "type": "function",
            "name": "getparams",
            "description": "Returns the parameters of a method or function.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Python object to get the parameters. Must be available considering the current scope.",
                    },
                },
                "additionalProperties": False,
                "required": ["object"],
            }
        },
        {
            "type": "function",
            "name": "list_fonts",
            "description": "Lists the available fonts for `Text` mobject.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": [],
            },
        },
        {
            "type": "function",
            "name": "try_latex_text",
            "description": "Tests if a LaTeX text mode string is valid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "LaTeX text mode string to test.",
                    },
                },
                "additionalProperties": False,
                "required": ["text"],
            },
        },
        {
            "type": "function",
            "name": "try_latex_math",
            "description": "Tests if a LaTeX math mode string is valid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "math": {
                        "type": "string",
                        "description": "LaTeX math mode string to test.",
                    },
                },
                "required": ["math"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "eval",
            "description": "Evaluates a Python expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Python expression to evaluate.",
                    },
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "finish",
            "description": "Finishes the scene rendering.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    ]
    """Scene class for rendering responses."""

    def __init__(self, title: str, description: str, type: str, data: list[dict[str, Any]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._internal_title = title
        self._internal_description = description
        self._internal_data = data
        self._internal_type = type
        self._internal_finished: bool = False
        self._internal_successful_data = []
        self._internal_reset_scope()
    
    def _internal_reset_scope(self) -> None:
        """Resets the scope to the initial state."""
        self._internal_scope = {}
        self._internal_scope.update(manim.__dict__)
        self._internal_scope.update({"math": math, "np": np, "random": random, "sympy": sympy})
        self._internal_scope["self"] = self

    def construct(self) -> None:
        if self._internal_data is None:
            self._internal_get_data()
        else:
            self._internal_construct_with_data()
    
    def _internal_get_data(self) -> None:
        global MANIM_BUILDER_FORMATTED_INSTRUCTIONS
        if self._internal_prompt_count > self._internal_prompt_limit:
            self._internal_manim_builder_previous_response_id = None
            self._internal_prompt_count = 0
            MANIM_BUILDER_FORMATTED_INSTRUCTIONS = MANIM_BUILDER_INSTRUCTIONS.format(
                rag_dataset=load_manim_rag_dataset()
            )
        self._internal_successful_data = []
        sio = StringIO()
        json.dump({
            "title": self._internal_title,
            "description": self._internal_description,
            "type": self._internal_type,
        }, sio, ensure_ascii=False, indent=4)
        sio.seek(0)
        first_time: bool = True
        while not self._internal_finished:
            self._internal_prompt_count += 1
            response = client.responses.create(
                model="gpt-4.1",
                instructions=MANIM_BUILDER_FORMATTED_INSTRUCTIONS,
                input=sio.getvalue() if first_time else outputs,
                temperature=0.0,
                tools=self._internal_tools,
                previous_response_id=self._internal_manim_builder_previous_response_id,
            )
            outputs = []
            first_time = False
            response_id = response.id
            self._internal_manim_builder_previous_response_id = response_id
            output = response.output
            for item in output:
                if not isinstance(item, dict):
                    item = item.to_dict(mode="json")
                if item["type"] == "function_call":
                    name = item["name"]
                    arguments = json.loads(item["arguments"])
                    if name == "exec_python":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_exec_python(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "scope":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_show_scope()
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "dir":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_show_dir(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "doc":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_show_doc(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "getparams":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_show_params(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "list_fonts":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_list_fonts()
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "try_latex_text":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_try_latex_text(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "try_latex_math":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_try_latex_math(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "eval":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_eval(**arguments)
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                    elif name == "finish":
                        time.sleep(2.0)  # Avoid hitting the API too fast
                        out = self._internal_finish_scene()
                        outputs.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": out,
                        })
                contents = item.get("content", None)
                if contents:
                    for content in contents:
                        if content["type"] == "output_text":
                            print(content["text"])
            time.sleep(2.0)  # Avoid hitting the API too fast
    
    def _internal_construct_with_data(self) -> None:
        for item in self._internal_data:
            exec(item["code"], self._internal_scope)

    def _internal_exec_python(self, code: str) -> str:
        """Executes Python code."""
        self.clear()
        self._internal_reset_scope()
        for item in self._internal_successful_data:
            exec(item["code"], self._internal_scope)
        try:
            exec(code, self._internal_scope)
        except Exception as e:
            print("Error executing code\n" + str(type(e)) + ": " + str(e))
            return "Error executing code\n" + str(type(e)) + ": " + str(e)
        else:
            self._internal_successful_data.append(
                {
                    "code": code,
                }
            )
            print("Code executed successfully.")
            return "Code executed successfully."
    
    def _internal_show_scope(self) -> str:
        print("Scope:", self._internal_scope)
        return str(self._internal_scope)
    
    def _internal_show_dir(self, object: str) -> str:
        try:
            obj = eval(object, self._internal_scope)
            print("Dir:", dir(obj))
            return str(dir(obj))
        except Exception as e:
            print(f"{type(e)}: {e}")
            return "An error occurred while trying to get the dir of {object}.\n" + str(type(e)) + ": " + str(e)
    
    def _internal_show_doc(self, object: str) -> str:
        try:
            obj = eval(object, self._internal_scope)
            doc = getattr(obj, "__doc__", None)
            if doc:
                print("Doc:", doc)
                return str(doc)
            else:
                print(f"No docstring found for {object}, but it exists.")
                return f"No docstring found for {object}, but it exists."
        except Exception as e:
            print(f"{type(e)}: {e}")
            return f"An error occurred while trying to get the docstring of {object}.\n" + str(type(e)) + ": " + str(e)
    
    def _internal_show_params(self, object: str) -> str:
        try:
            obj = eval(object, self._internal_scope)
            if not callable(obj):
                print(f"Object {object} is not callable.")
                return f"Object {object} is not callable."
            params = inspect.getfullargspec(obj).args
            if params:
                print("Params:", params)
                return str(params)
            else:
                print(f"Function {object} has no parameters. Call it using `()`.")
                return f"Function {object} has no parameters. Call it using `()`. "
        except Exception as e:
            print(f"{type(e)}: {e}")
            return f"An error occurred while trying to get the parameters of {object}.\n" + str(type(e)) + ": " + str(e)
    
    def _internal_list_fonts(self) -> str:
        fonts = manimpango.list_fonts()
        print("Fonts:", fonts)
        return str(fonts)
    
    def _internal_try_latex_text(self, text: str) -> str:
        try:
            manim.Tex(text)
            print("LaTeX text mode string is valid.")
            return "LaTeX text mode string is valid."
        except Exception as e:
            print("LaTeX text mode string is invalid.\n" + str(type(e)) + ": " + str(e))
            return "LaTeX text mode string is invalid.\n" + str(type(e)) + ": " + str(e)
        
    def _internal_try_latex_math(self, math: str) -> str:
        try:
            manim.MathTex(math)
            print("LaTeX math mode string is valid.")
            return "LaTeX math mode string is valid."
        except Exception as e:
            print("LaTeX math mode string is invalid.\n" + str(type(e)) + ": " + str(e))
            return "LaTeX math mode string is invalid.\n" + str(type(e)) + ": " + str(e)
    
    def _internal_eval(self, expression: str) -> str:
        try:
            code = expression.split("\n")
            exec("\n".join(code[:-1]), self._internal_scope)
            obj = eval(code[-1], self._internal_scope)
            print("Eval:", obj)
            return str(obj)
        except Exception as e:
            print(f"An error occurred while trying to evaluate {expression}.\n" + str(type(e)) + ": " + str(e))
            return f"An error occurred while trying to evaluate {expression}.\n" + str(type(e)) + ": " + str(e)
    
    def _internal_finish_scene(self) -> str:
        self._internal_finished = True
        print("Scene finished.")
        return "Scene finished."


class ResponseScene3D(manim.ThreeDScene, ResponseScene):
    """3D version of the ResponseScene."""
    pass


def get_code_template(scene: ResponseScene | ResponseScene3D) -> str:
    base_class_name = "ThreeDScene" if isinstance(scene, ResponseScene3D) else "Scene"
    code = "\n".join([
        " " * 8 + line for piece in scene._internal_data for line in piece["code"].split("\n")
    ])
    full_code = f"""
from manim import *
import math
import numpy as np
import random
import sympy


class ResponseScene({base_class_name}):
    def construct(self) -> None:
{code}
""".strip()
    return full_code


def load_manim_rag_dataset() -> str:
    """Load the Manim dataset, with well-done examples."""
    # Select videos with feedback greater than 0.7
    dataset = (
        supabase
        .table("videos_dataset")
        .select("*")
        .filter("feedback", "gt", 0.7)
        .filter("total_votes", "gt", 1)
        .execute()
    )
    dataset = dataset.data
    if len(dataset) == 0:
        return ""
    taken = [(row["title"], row["description"], row["code"]) for row in dataset]
    formatted_examples = []
    for title, description, code in taken:
        formatted_examples.append(
            f"- **Title**: {title}\n"
            f"  **Description**: {description}\n"
            f"  **Code**:\n"
            f"  ```python\n{code}\n```\n"
        )
    formatted_examples = "\n\n".join(formatted_examples)
    
    rag_dataset = f"""
Here you will see well done examples with title, description, and the code snippet that well done the job:

{formatted_examples}
"""
    return rag_dataset


MANIM_BUILDER_FORMATTED_INSTRUCTIONS: str = MANIM_BUILDER_INSTRUCTIONS.format(
    rag_dataset=load_manim_rag_dataset()
)


async def render_manim(
    message: discord.Message,
    title: str,
    description: str,
    is_3d: bool,
    type: str
) -> str:
    """Render a Manim scene and send it to the Discord channel."""
    try:
        scene = ResponseScene3D if is_3d else ResponseScene
        manim.config.output_file = scene.__name__
        manim.config.write_to_movie = True
        scene_instance = scene(
            title=title,
            description=description,
            type=type,
            data=None,
        )
        scene_instance.render()
        scene = ResponseScene3D if is_3d else ResponseScene
        scene_instance = scene(
            title=title,
            description=description,
            type=type,
            data=scene_instance._internal_successful_data,
        )
        code_template = get_code_template(scene_instance)
        scene_instance.render()
        if type == "video":
            path = pathlib.Path("media") / "videos" / "1080p60" / f"{scene.__name__}.mp4"
            if not path.exists():
                return "The video was not rendered. Please try again."
            with open(path, "rb") as f:
                msg = await message.reply(content="Reacciona a este mensaje, por favor. Tu feedback es importante.", file=discord.File(fp=f, filename=f"{title}.mp4"))
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            supabase.table("videos_dataset").insert(
                {
                    "title": title,
                    "description": description,
                    "code": "\n\n".join([data["code"] for data in scene_instance._internal_data]),
                    "positive_votes": 0,
                    "total_votes": 0,
                    "feedback": None,
                    "id": str(msg.id),
                }
            ).execute()
            return (
                "The video was rendered successfully. The user must watch it in the sent message.\n"
                + "The code to build the scene is:\n```python\n" \
                + code_template
                + "```"
            )
        else:
            path = pathlib.Path("media") / "images" / f"{scene.__name__}.png"
            if not path.exists():
                return "The image was not rendered. Please try again."
            with open(path, "rb") as f:
                msg = await message.reply(content="Reacciona a este mensaje, por favor. Tu feedback es importante.", file=discord.File(fp=f, filename=f"{title}.png"))
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            supabase.table("videos_dataset").insert(
                {
                    "title": title,
                    "description": description,
                    "code": "\n\n".join([data["code"] for data in scene_instance._internal_data]),
                    "positive_votes": 0,
                    "total_votes": 0,
                    "feedback": None,
                    "id": str(msg.id),
                }
            ).execute()
            return (
                "The image was rendered successfully. The user must watch it in the sent message.\n"
                + "The code to build the scene is:\n```python\n" \
                + code_template
                +"```"
            )
    except Exception as e:
        print(f"Error rendering Manim scene: {e}")
        return "An error occurred while rendering the Manim scene. Please try again."


last_math_response_id: str | None = None
prompt_count: int = 0
prompt_limit: int = 500


def solve_math(
    problem_statement: str
) -> str:
    """Create a math response using reasoning model."""
    global last_math_response_id, prompt_count, prompt_limit
    prompt_count += 1
    if prompt_count > prompt_limit:
        last_math_response_id = None
        prompt_count = 0
    try:
        there_was_function_call: bool = True
        text_parts = []
        while there_was_function_call:
            there_was_function_call = False
            response = client.responses.create(
                model="gpt-4.1",
                instructions=MATH_SOLVE_INSTRUCTIONS,
                input=problem_statement,
                temperature=0.0,
                previous_response_id=last_math_response_id,
                tools=[
                    {
                        "type": "function",
                        "name": "sympy_calculator",
                        "description": "Calculates mathematical expressions using Python and SymPy, NumPy and math module.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Python expression to evaluate..",
                                },
                            },
                            "required": ["expression"],
                            "additionalProperties": False,
                        },
                    },
                ],
            )
            last_math_response_id = response.id
            output = response.output
            problem_statement = []
            for item in output:
                if not isinstance(item, dict):
                    item = item.to_dict(mode="json")
                if item.get("type") == "function_call":
                    name = item["name"]
                    arguments = json.loads(item["arguments"])
                    if name == "sympy_calculator":
                        expression = arguments["expression"]
                        print("Expression:", expression)
                        try:
                            scope = {"sympy": sympy, "math": math, "np": np}
                            code = expression.split("\n")
                            exec("\n".join(code[:-1]), scope)
                            result = str(eval(code[-1], scope))
                        except Exception as e:
                            result = f"{type(e)}: {e}"
                        print("Result:", result)
                        problem_statement.append({
                            "type": "function_call_output",
                            "call_id": item["call_id"],
                            "output": result,
                        })
                        response_id = response.id
                        last_math_response_id = response_id
                        there_was_function_call = True
                content = item.get("content", None)
                if content:
                    for content_item in content:
                        if content_item["type"] == "output_text":
                            print(content_item["text"])
                            text_parts.append(content_item["text"])
            time.sleep(2.0)  # Avoid hitting the API too fast
        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"Error solving math problem: {e}")
        return "An error occurred while solving the math problem. Please try again."
