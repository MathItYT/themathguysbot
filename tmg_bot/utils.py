import discord
import emoji
import pathlib
import subprocess
import base64
import os
import json
import requests
from typing import Any
import manim
import math
import numpy as np
import sympy
import time
from manimpango import list_fonts

from .function_plot import FunctionPlot
from .title_animation import TitleAnimation
from .tex_templates import DEFAULT_TEX_TEMPLATE
from .instructions import (
    TEXT_TO_LATEX_INSTRUCTIONS,
    MANIM_BUILDER_INSTRUCTIONS,
    CUSTOM_CODE_DEBUGGER_INSTRUCTIONS,
    PROBLEM_STATE_INSTRUCTIONS,
    MATH_SOLVE_INSTRUCTIONS,
    CODE_FIXER_INSTRUCTIONS
)
from .regex import mentions, double_quotes, single_quotes


async def attachment_parts(attachments: list[discord.Attachment]) -> list:
    """Convert attachments to parts for the Gemini API."""
    parts = []
    for attachment in attachments:
        parts.append(
            {
                "inline_data": {
                    "data": base64.b64encode(await attachment.read()).decode("utf-8"),
                    "mime_type": attachment.content_type,
                }
            }
        )
    return parts


def fix_tex_bugs(text: str) -> str:
    without_emojis = emoji.replace_emoji(text, "")
    without_mentions = mentions.sub("Usuario de Discord", without_emojis)
    beautify_quotes = double_quotes.sub(r"“\1”", without_mentions)
    beautify_quotes = single_quotes.sub(r"‘\1’", beautify_quotes)
    return beautify_quotes


async def render_tex(message: discord.Message, contents: str) -> None:
    temp_dir: pathlib.Path = pathlib.Path("temp")
    temp_dir.mkdir(exist_ok=True)
    md = fix_tex_bugs(contents)
    channel = message.channel
    author = message.author
    temp_tex = temp_dir / f"{message.id}.tex"
    temp_png = temp_dir / f"{message.id}.png"
    temp_tex.write_text(DEFAULT_TEX_TEMPLATE.format(md=md), encoding="utf-8")
    try:
        for _ in range(2):
            subprocess.run(" ".join(["cd", "temp", "&&", "latex", "-interaction=nonstopmode", "-shell-escape", f"{message.id}.tex"]), check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error rendering LaTeX: {e}")
        return
    try:
        subprocess.run(" ".join(["cd", "temp", "&&", "dvipng", "-T", "tight", "-o", f"{message.id}.png", "-bg", "Transparent", "-D", "500", f"{message.id}.dvi"]), check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error rendering LaTeX: {e}")
        return
    with open(temp_png, "rb") as f:
        if isinstance(channel, discord.DMChannel):
            await author.send(file=discord.File(f, "texput.png"), reference=message)
        else:
            await channel.send(file=discord.File(f, "texput.png"), reference=message)


def internet_search(query: str) -> dict[str, str]:
    search_response = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": os.getenv("GOOGLE_API_KEY"),
            "cx": os.getenv("GOOGLE_CX"),
            "q": query,
        },
        headers={"Content-Type": "application/json"},
    )
    search_response.raise_for_status()
    search_results = search_response.json()
    items = search_results.get("items", [])
    if not items:
        return {"error": "No se encontraron resultados."}
    results = []
    max_results: int = 10
    for item in items:
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet")
        results.append(f"# {title}\n{snippet}\nLink: {link}")
        if len(results) >= max_results:
            break
    return {"results": results}


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


class TimeoutError(Exception):
    """Custom exception for timeout errors."""
    pass


class ResponseScene(manim.Scene):
    select_template_history: list[dict[str, Any]] = []
    debugger_history: list[dict[str, Any]] = []
    """Scene class for rendering responses."""

    def __init__(self, title: str, description: str, steps: list[str], considerations: list[str], data: list[dict[str, Any]] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.description = description
        self.steps = steps
        self.considerations = considerations
        self.data = data
        self.successful_data = []

    def construct(self) -> None:
        self.stamp = time.time()
        self.add_updater(lambda _: self.check_for_timeout())
        if self.data is not None:
            title = self.create_title(self.title)
            description = self.create_description(self.description)
            self.arrange_objects([title, description], layout="vertical", buff=0.5)
            self.play(TitleAnimation(title))
            self.play(manim.AddTextLetterByLetter(description[0], run_time=2))
            self.wait(1)
            self.fade_out_scene()
            for i, data in enumerate(self.data, start=1):
                self.show_step(data["step"], i)
                if data["name"] == "custom_template":
                    self.custom_template(data["step"], data["args"]["code"])
                elif data["name"] == "plot_single_variable_and_output_real_continuous_function":
                    function = data["args"]["function"]
                    x_min = data["args"]["x_min"]
                    x_max = data["args"]["x_max"]
                    x_step = data["args"]["x_step"]
                    y_min = data["args"]["y_min"]
                    y_max = data["args"]["y_max"]
                    y_step = data["args"]["y_step"]
                    x_label = data["args"]["x_label"]
                    y_label = data["args"]["y_label"]
                    discontinuities = data["args"]["discontinuities"]
                    function_color = data["args"]["function_color"]
                    x_length = data["args"]["x_length"]
                    y_length = data["args"]["y_length"]
                    step = data["step"]
                    self.plot_single_variable_and_output_real_continuous_function(
                        step=step,
                        function=function,
                        x_min=x_min,
                        x_max=x_max,
                        x_step=x_step,
                        y_min=y_min,
                        y_max=y_max,
                        y_step=y_step,
                        x_label=x_label,
                        y_label=y_label,
                        discontinuities=discontinuities,
                        function_color=function_color,
                        x_length=x_length,
                        y_length=y_length,
                    )
                elif data["name"] == "plot_implicit_curve_2d":
                    function = data["args"]["function"]
                    x_min = data["args"]["x_min"]
                    x_max = data["args"]["x_max"]
                    x_step = data["args"]["x_step"]
                    y_min = data["args"]["y_min"]
                    y_max = data["args"]["y_max"]
                    y_step = data["args"]["y_step"]
                    x_label = data["args"]["x_label"]
                    y_label = data["args"]["y_label"]
                    function_color = data["args"]["function_color"]
                    x_length = data["args"]["x_length"]
                    y_length = data["args"]["y_length"]
                    step = data["step"]
                    self.plot_implicit_curve_2d(
                        step=step,
                        function=function,
                        x_min=x_min,
                        x_max=x_max,
                        x_step=x_step,
                        y_min=y_min,
                        y_max=y_max,
                        y_step=y_step,
                        x_label=x_label,
                        y_label=y_label,
                        function_color=function_color,
                        x_length=x_length,
                        y_length=y_length,
                    )
                elif data["name"] == "show_sphere":
                    color_1 = data["args"]["color_1"]
                    color_2 = data["args"]["color_2"]
                    step = data["step"]
                    self.show_sphere(
                        step=step,
                        color_1=color_1,
                        color_2=color_2,
                    )
                elif data["name"] == "pi_approximation_by_monte_carlo":
                    n_points_in_square = data["args"]["n_points_in_square"]
                    color_square = data["args"]["color_square"]
                    color_circle = data["args"]["color_circle"]
                    step = data["step"]
                    self.pi_approximation_by_monte_carlo(
                        step=step,
                        n_points_in_square=n_points_in_square,
                        color_square=color_square,
                        color_circle=color_circle,
                    )
                else:
                    print(f"Unknown data name: {data['name']}")
                self.fade_out_scene()
            return
        
        steps = "\n".join([f"{i}. {s}" for i, s in enumerate(self.steps, start=1)])
        ResponseScene.select_template_history.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"""Now we're building a totally new scene.

This is the title:
```
{self.title}
```

This is the description:
```
{self.description}
```

Here are all the steps:
```
{steps}
```

Methods and attributes available for `self` are:
```
{dir(self)}
```

Camera methods and attributes available are:
```
{dir(self.camera)}
```

Available fonts for `Text` object are:
```
{list_fonts()}
```
"""
                    }
                ]
            }
        )
        for i, step in enumerate(self.steps, start=1):
            self.make_step(step, i)
    
    def check_for_timeout(self) -> None:
        """Check if the scene is taking too long to render (more than 2 minutes)"""
        if time.time() - self.stamp > 120:
            raise TimeoutError("The maximum time for rendering scenes is 2 minutes. Please render scenes that aren't that heavy.")
    
    def make_step(self, step: str, index: int) -> None:
        self.select_template(step, index)
        self.fade_out_scene()

    def select_template(self, step: str, index: int) -> None:
        considerations = "\n".join(self.considerations) if len(self.considerations) > 0 else ""
        all_steps = "\n".join([f"{i}. {s}" for i, s in enumerate(self.steps, start=1)])
        ResponseScene.select_template_history.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"""
Here are all the steps:
```
{all_steps}
```

And the current step is:
```
{index}. {step}
```

Choose a template to use for the current step. The templates are your tools.

You're allowed to choose a template for doing multiple steps at once, but you must do nothing when some next step is related to the previous one and you did that step with the previous template, don't do the same again.
""" + "" if len(self.considerations) == 0 else f"""

And the considerations are:
```
{considerations}
```

Remember available methods and attributes for `self` are:
```
{dir(self)}
```

Camera methods and attributes available are:
```
{dir(self.camera)}
```

And available fonts for `Text` object are:

```
{list_fonts()}
```
"""
                    }
                ]
            }
        )
        there_was_function_call: bool = False
        while not there_was_function_call:
            select_template_response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
                params={
                    "key": os.getenv("GOOGLE_API_KEY"),
                },
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {
                        "parts": [
                            {
                                "text": MANIM_BUILDER_INSTRUCTIONS,
                            },
                        ]
                    },
                    "contents": ResponseScene.select_template_history,
                    "tools": [
                        {
                            "functionDeclarations": [
                                {
                                    "name": "custom_template",
                                    "description": "Custom template if the situation doesn't match any of the other templates.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "code": {
                                                "type": "STRING",
                                                "description": "Partial Python code to run.",
                                            }
                                        },
                                        "required": ["code"],
                                    },
                                },
                                {
                                    "name": "plot_single_variable_and_output_real_continuous_function",
                                    "description": "Single variable and output real continuous function.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "function": {
                                                "type": "STRING",
                                                "description": "Function to plot as a Python string, depends on `x` variable, which is already in the scope. You have access to `math` module, so you can use it directly (e.g. `math.sin(x)` or `math.sqrt(x)`).",
                                            },
                                            "x_min": {
                                                "type": "NUMBER",
                                                "description": "Minimum value of x.",
                                            },
                                            "x_max": {
                                                "type": "NUMBER",
                                                "description": "Maximum value of x.",
                                            },
                                            "x_step": {
                                                "type": "NUMBER",
                                                "description": "Tick step of x. It's NOT the step of function plotting. So it should be a reasonable number to have from 5 to 10 x ticks in the plot.",
                                            },
                                            "y_min": {
                                                "type": "NUMBER",
                                                "description": "Minimum value of y.",
                                            },
                                            "y_max": {
                                                "type": "NUMBER",
                                                "description": "Maximum value of y.",
                                            },
                                            "y_step": {
                                                "type": "NUMBER",
                                                "description": "Tick step of y. It's NOT the step of function plotting. So it should be a reasonable number to have from 5 to 10 y ticks in the plot.",
                                            },
                                            "x_label": {
                                                "type": "STRING",
                                                "description": "Label for x axis in LaTeX math mode.",
                                            },
                                            "y_label": {
                                                "type": "STRING",
                                                "description": "Label for y axis in LaTeX math mode.",
                                            },
                                            "discontinuities": {
                                                "type": "ARRAY",
                                                "items": {
                                                    "type": "NUMBER",
                                                    "description": "Discontinuity of the function.",
                                                },
                                                "description": "Discontinuities of the function.",
                                            },
                                            "function_color": {
                                                "type": "STRING",
                                                "description": "Color of the function. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them.",
                                            },
                                            "x_length": {
                                                "type": "NUMBER",
                                                "description": "Length of x axis.",
                                            },
                                            "y_length": {
                                                "type": "NUMBER",
                                                "description": "Length of y axis.",
                                            },
                                        },
                                        "required": ["function", "x_min", "x_max", "x_step", "y_min", "y_max", "y_step", "x_label", "y_label", "discontinuities", "function_color", "x_length", "y_length"],
                                    },
                                },
                                {
                                    "name": "plot_implicit_curve_2d",
                                    "description": "Implicit curve 2D.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "function": {
                                                "type": "STRING",
                                                "description": "Function to plot as a Python string, depends on `x` variable and `y` variable, which are already in the scope. You have access to `math` module, so you can use it directly (e.g. `math.sin(x + y)` or `math.sqrt(x^2 - y^2)`). The implicit function is defined as `f(x, y) = 0`, so you need to define it as such. Here goes f(x, y).",
                                            },
                                            "x_min": {
                                                "type": "NUMBER",
                                                "description": "Minimum value of x.",
                                            },
                                            "x_max": {
                                                "type": "NUMBER",
                                                "description": "Maximum value of x.",
                                            },
                                            "x_step": {
                                                "type": "NUMBER",
                                                "description": "Tick step of x. It's NOT the step of function plotting. So it should be a reasonable number to have from 5 to 10 x ticks in the plot.",
                                            },
                                            "y_min": {
                                                "type": "NUMBER",
                                                "description": "Minimum value of y.",
                                            },
                                            "y_max": {
                                                "type": "NUMBER",
                                                "description": "Maximum value of y.",
                                            },
                                            "y_step": {
                                                "type": "NUMBER",
                                                "description": "Tick step of y. It's NOT the step of function plotting. So it should be a reasonable number to have from 5 to 10 y ticks in the plot.",
                                            },
                                            "x_label": {
                                                "type": "STRING",
                                                "description": "Label for x axis in LaTeX math mode.",
                                            },
                                            "y_label": {
                                                "type": "STRING",
                                                "description": "Label for y axis in LaTeX math mode.",
                                            },
                                            "function_color": {
                                                "type": "STRING",
                                                "description": "Color of the function. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them.",
                                            },
                                            "x_length": {
                                                "type": "NUMBER",
                                                "description": "Length of x axis.",
                                            },
                                            "y_length": {
                                                "type": "NUMBER",
                                                "description": "Length of y axis.",
                                            },
                                        },
                                        "required": ["function", "x_min", "x_max", "x_step", "y_min", "y_max", "y_step", "x_label", "y_label", "function_color", "x_length", "y_length"],
                                    },
                                },
                                {
                                    "name": "show_sphere",
                                    "description": "Shows a sphere and rotates camera to enhance 3D view.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "color_1": {
                                                "type": "STRING",
                                                "description": "First color of the sphere's checkerboard fill. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them. Preferably use BLUE_D.",
                                            },
                                            "color_2": {
                                                "type": "STRING",
                                                "description": "Second color of the sphere's checkerboard fill. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them. Preferably use BLUE_E.",
                                            },
                                        },
                                        "required": ["color_1", "color_2"],
                                    }
                                },
                                {
                                    "name": "pi_approximation_by_monte_carlo",
                                    "description": "Animation of pi approximation by Monte Carlo method.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "n_points_in_square": {
                                                "type": "NUMBER",
                                                "description": "Number of points to be generated in the square. The limit is 200 points.",
                                            },
                                            "color_square": {
                                                "type": "STRING",
                                                "description": "Color of points in the square, but not part of the circle. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them. Preferably use BLUE.",
                                            },
                                            "color_circle": {
                                                "type": "STRING",
                                                "description": "Color of points inside the circle. Must be a built-in Manim color. (e.g. WHITE, RED, BLUE, etc.). If user specifies a color, put it as a valid hex color between quotes (e.g. '#FF0000'), without escaping them. Preferably use RED.",
                                            },
                                        },
                                        "required": ["n_points_in_square", "color_square", "color_circle"],
                                    }
                                },
                                {
                                    "name": "do_nothing",
                                    "description": "Do nothing. Meant to be used when already did the step with the previous template.",
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "reason": {
                                                "type": "STRING",
                                                "description": "Reason why you did nothing.",
                                            },
                                        },
                                        "required": ["reason"],
                                    },
                                }
                            ]
                        }
                    ],
                }
            )
            select_template_results = select_template_response.json()
            print(select_template_results)
            select_template_response.raise_for_status()
            content = select_template_results["candidates"][0]["content"]
            parts = content["parts"]
            ResponseScene.select_template_history.append(content)
            for part in parts:
                if "functionCall" in part:
                    there_was_function_call = True
                    name = part["functionCall"]["name"]
                    args = part["functionCall"]["args"]
                    if name == "custom_template":
                        self.custom_template(step, args["code"])
                    elif name == "plot_single_variable_and_output_real_continuous_function":
                        function = args["function"]
                        x_min = args["x_min"]
                        x_max = args["x_max"]
                        y_min = args["y_min"]
                        y_max = args["y_max"]
                        x_label = args["x_label"]
                        y_label = args["y_label"]
                        discontinuities = args["discontinuities"]
                        function_color = args["function_color"]
                        x_step = args["x_step"]
                        y_step = args["y_step"]
                        x_length = args["x_length"]
                        y_length = args["y_length"]
                        self.plot_single_variable_and_output_real_continuous_function(
                            function=function,
                            x_min=x_min,
                            x_max=x_max,
                            x_step=x_step,
                            y_min=y_min,
                            y_max=y_max,
                            y_step=y_step,
                            x_label=x_label,
                            y_label=y_label,
                            discontinuities=discontinuities,
                            function_color=function_color,
                            step=step,
                            x_length=x_length,
                            y_length=y_length,
                        )
                    elif name == "plot_implicit_curve_2d":
                        function = args["function"]
                        x_min = args["x_min"]
                        x_max = args["x_max"]
                        y_min = args["y_min"]
                        y_max = args["y_max"]
                        x_label = args["x_label"]
                        y_label = args["y_label"]
                        function_color = args["function_color"]
                        x_step = args["x_step"]
                        y_step = args["y_step"]
                        x_length = args["x_length"]
                        y_length = args["y_length"]
                        self.plot_implicit_curve_2d(
                            function=function,
                            x_min=x_min,
                            x_max=x_max,
                            x_step=x_step,
                            y_min=y_min,
                            y_max=y_max,
                            y_step=y_step,
                            x_label=x_label,
                            y_label=y_label,
                            function_color=function_color,
                            step=step,
                            x_length=x_length,
                            y_length=y_length,
                        )
                    elif name == "show_sphere":
                        color_1 = args["color_1"]
                        color_2 = args["color_2"]
                        self.show_sphere(
                            color_1=color_1,
                            color_2=color_2,
                            step=step,
                        )
                    elif name == "pi_approximation_by_monte_carlo":
                        n_points_in_square = args["n_points_in_square"]
                        color_square = args["color_square"]
                        color_circle = args["color_circle"]
                        self.pi_approximation_by_monte_carlo(
                            n_points_in_square=n_points_in_square,
                            color_square=color_square,
                            color_circle=color_circle,
                            step=step,
                        )
                    elif name == "do_nothing":
                        reason = args["reason"]
                        print(f"Do nothing's reason: {reason}")
                    else:
                        print(f"Unknown function call: {name}")
                if "text" in part:
                    text = part["text"]
                    print(f"Text: {text}")
            if not there_was_function_call:
                ResponseScene.select_template_history.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": """
Do it. Execute the tool.
"""
                            }
                        ]
                    }
                )
    
    def custom_template(self, step: str, code: str) -> None:
        """Execute the custom template code."""
        try:
            scope = manim.__dict__.copy()
            scope["self"] = self
            scope["TitleAnimation"] = TitleAnimation
            scope["FunctionPlot"] = FunctionPlot
            scope["math"] = math
            exec(code, scope)
            if self.data is None:
                ResponseScene.select_template_history.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": "custom_template",
                                    "response": {
                                        "name": "custom_template",
                                        "content": "The code was executed successfully.",
                                    }
                                }
                            }
                        ]
                    }
                )
                self.successful_data.append(
                    {
                        "name": "custom_template",
                        "args": {
                            "code": code,
                        },
                        "step": step,
                    }
                )
            return
        except TimeoutError as e:
            print("TimeoutError: The maximum time for rendering scenes is 2 minutes. Please render scenes that aren't that heavy.")
            if self.data is None:
                ResponseScene.select_template_history.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": "custom_template",
                                    "response": {
                                        "name": "custom_template",
                                        "content": f"TimeoutError: {e}\nWhen timeout is reached, your work for the scene is discarded and finished, so it's not possible to continue working on it.",
                                    }
                                }
                            }
                        ]
                    }
                )
            raise e
        except Exception as e:
            error_message = f"{type(e).__name__}: {e}"
            print(f"Error message: {error_message}")
            error: bool = True
            while error:
                success = self.debug_custom_code(step, code, error_message)
                if success:
                    error = False
    
    def plot_single_variable_and_output_real_continuous_function(
        self,
        step: str,
        function: str,
        x_min: float,
        x_max: float,
        x_step: float,
        y_min: float,
        y_max: float,
        y_step: float,
        x_label: str,
        y_label: str,
        discontinuities: list[float],
        function_color: str,
        x_length: float,
        y_length: float,
    ) -> None:
        function_color = function_color if not function_color.startswith("#") else f"'{function_color}'"

        def include_in_scope(scope: dict[str, Any], name: str, value: Any) -> dict[str, Any]:
            scope[name] = value
            return scope

        ax = manim.Axes(
            x_range=(x_min, x_max, x_step),
            y_range=(y_min, y_max, y_step),
            x_length=8 * x_length / y_length,
            y_length=8,
        )

        def f(x: float) -> float:
            point = ax.c2p(x, eval(function, include_in_scope(math.__dict__.copy(), "x", x)))
            return (point[0], point[1])
        
        color = eval(function_color, manim.__dict__.copy())
        ax.add_coordinates()
        axis_labels = ax.get_axis_labels(x_label, y_label)
        ax.add(axis_labels)
        plot = FunctionPlot(
            f,
            discontinuities=discontinuities,
            t_domain=(x_min, x_max),
            x_range=(ax.c2p(x_min, y_min)[0], ax.c2p(x_max, y_max)[0], 0.01),
            y_range=(ax.c2p(x_min, y_min)[1], ax.c2p(x_max, y_max)[1], 0.01),
        ).set_color(color)
        self.ensure_in_frame(manim.VGroup(ax, plot), padding=1.5)
        self.play(manim.Write(ax))
        self.play(manim.Create(plot))
        self.wait(2)
        if self.data is None:
            self.successful_data.append(
                {
                    "name": "plot_single_variable_and_output_real_continuous_function",
                    "args": {
                        "function": function,
                        "x_min": x_min,
                        "x_max": x_max,
                        "x_step": x_step,
                        "y_min": y_min,
                        "y_max": y_max,
                        "y_step": y_step,
                        "x_label": x_label,
                        "y_label": y_label,
                        "discontinuities": discontinuities,
                        "function_color": function_color,
                        "x_length": x_length,
                        "y_length": y_length,
                    },
                    "step": step,
                }
            )
            ResponseScene.select_template_history.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "plot_single_variable_and_output_real_continuous_function",
                                "response": {
                                    "name": "plot_single_variable_and_output_real_continuous_function",
                                    "content": f"""The function was plotted successfully.

This is equivalent to the following custom template:
```python
ax = Axes(
    x_range=({x_min}, {x_max}, {x_step}),
    y_range=({y_min}, {y_max}, {y_step}),
    x_length=8 * {x_length} / {y_length},
    y_length=8,
)

def f(x: float) -> float:
    point = ax.c2p(x, {function})
    return (point[0], point[1])

    
color = {function_color}
ax.add_coordinates()
axis_labels = ax.get_axis_labels({repr(x_label)}, {repr(y_label)})
ax.add(axis_labels)
plot = FunctionPlot(
    f,
    discontinuities={repr(discontinuities)},
    t_domain=({x_min}, {x_max}),
    x_range=(ax.c2p({x_min}, {y_min})[0], ax.c2p({x_max}, {y_max})[0], 0.01),
    y_range=(ax.c2p({x_min}, {y_min})[1], ax.c2p({x_max}, {y_max})[1], 0.01),
).set_color(color)
self.ensure_in_frame(VGroup(ax, plot), padding=1.5)
self.play(Write(ax))
self.play(Create(plot))
self.wait(2)
```
""",
                                }
                            }
                        }
                    ]
                }
            )

    def plot_implicit_curve_2d(
        self,
        step: str,
        function: str,
        x_min: float,
        x_max: float,
        x_step: float,
        y_min: float,
        y_max: float,
        y_step: float,
        x_label: str,
        y_label: str,
        function_color: str,
        x_length: float,
        y_length: float,
    ) -> None:
        function_color = function_color if not function_color.startswith("#") else f"'{function_color}'"

        def include_in_scope(scope: dict[str, Any], data_to_add: dict[str, Any]) -> dict[str, Any]:
            scope.update(data_to_add)
            return scope

        ax = manim.Axes(
            x_range=(x_min, x_max, x_step),
            y_range=(y_min, y_max, y_step),
            x_length=8 * x_length / y_length,
            y_length=8,
        )

        def f(x, y):
            return eval(function, include_in_scope(math.__dict__.copy(), {"x": x, "y": y}))

        color = eval(function_color, manim.__dict__.copy())
        ax.add_coordinates()
        axis_labels = ax.get_axis_labels(x_label, y_label)
        ax.add(axis_labels)
        plot = ax.plot_implicit_curve(
            f,
        ).set_color(color)
        self.ensure_in_frame(manim.VGroup(ax, plot), padding=1.5)
        self.play(manim.Write(ax))
        self.play(manim.Create(plot))
        self.wait(2)
        if self.data is None:
            self.successful_data.append(
                {
                    "name": "plot_implicit_curve_2d",
                    "args": {
                        "function": function,
                        "x_min": x_min,
                        "x_max": x_max,
                        "x_step": x_step,
                        "y_min": y_min,
                        "y_max": y_max,
                        "y_step": y_step,
                        "x_label": x_label,
                        "y_label": y_label,
                        "function_color": function_color,
                        "x_length": x_length,
                        "y_length": y_length,
                    },
                    "step": step,
                }
            )
            ResponseScene.select_template_history.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "plot_implicit_curve_2d",
                                "response": {
                                    "name": "plot_implicit_curve_2d",
                                    "content": f"""
The implicit curve was plotted successfully.

This is equivalent to the following custom template:

```python
ax = Axes(
    x_range=({x_min}, {x_max}, {x_step}),
    y_range=({y_min}, {y_max}, {y_step}),
    x_length=8 * {x_length} / {y_length},
    y_length=8,
)

def f(x, y):
    return {function}

color = {function_color}
ax.add_coordinates()
axis_labels = ax.get_axis_labels({repr(x_label)}, {repr(y_label)})
ax.add(axis_labels)

plot = ax.plot_implicit_curve(
    f,
).set_color(color)
self.ensure_in_frame(VGroup(ax, plot), padding=1.5)
self.play(Write(ax))
self.play(Create(plot))
self.wait(2)
```
"""
                                }
                            }
                        }
                    ]
                }
            )
    
    def show_sphere(
        self,
        step: str,
        color_1: str,
        color_2: str,
    ) -> None:
        color_1 = color_1 if not color_1.startswith("#") else f"'{color_1}'"
        color_2 = color_2 if not color_2.startswith("#") else f"'{color_2}'"
        manim_color_1 = eval(color_1, manim.__dict__.copy())
        manim_color_2 = eval(color_2, manim.__dict__.copy())
        sphere = manim.Sphere(
            checkerboard_colors=[manim_color_1, manim_color_2],
        )
        self.play(manim.Create(sphere))
        self.begin_3dillusion_camera_rotation(rate=2)
        self.wait(2)
        self.stop_3dillusion_camera_rotation()
        self.move_camera(phi=0, theta=-90 * manim.DEGREES, gamma=0, run_time=1)
        self.wait(2)
        if self.data is None:
            self.successful_data.append(
                {
                    "name": "show_sphere",
                    "args": {
                        "color_1": color_1,
                        "color_2": color_2,
                    },
                    "step": step,
                }
            )
            ResponseScene.select_template_history.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "show_sphere",
                                "response": {
                                    "name": "show_sphere",
                                    "content": f"""
The sphere was shown successfully.

This is equivalent to the following custom template:

```python
sphere = Sphere(
    checkerboard_colors=[{color_1}, {color_2}],
)
self.play(Create(sphere))

self.begin_3dillusion_camera_rotation(rate=2)
self.wait(2)
self.stop_3dillusion_camera_rotation()
# Back to default angles (phi=0, theta=-90 * DEGREES, gamma=0)
self.move_camera(phi=0, theta=-90 * DEGREES, gamma=0, run_time=1)
self.wait(2)
```
"""
                                }
                            }
                        }
                    ]
                }
            )

    def pi_approximation_by_monte_carlo(
        self,
        step: str,
        n_points_in_square: int,
        color_square: str,
        color_circle: str,
    ) -> None:
        import random
        color_circle = color_circle if not color_circle.startswith("#") else f"'{color_circle}'"
        color_square = color_square if not color_square.startswith("#") else f"'{color_square}'"
        sq = manim.Square(side_length=4).set_color(color_square)
        circ = manim.Circle(radius=2).set_color(color_circle)
        self.play(manim.Create(sq))
        self.play(manim.Create(circ))
        self.wait(2)

        added_pi_value = False
        points_in_circle = 0
        points_out_circle = 0

        manim_color_circle = eval(color_circle, manim.__dict__.copy())
        manim_color_square = eval(color_square, manim.__dict__.copy())

        for _ in range(n_points_in_square):
            x = random.uniform(-2, 2)
            y = random.uniform(-2, 2)
            point = manim.Dot(x * manim.RIGHT + y * manim.UP, radius=0.05)
            if (x ** 2 + y ** 2) <= 4:
                color = manim_color_circle
                point.set_color(color)
                points_in_circle += 1
                self.add(point)
            else:
                color = manim_color_square
                point.set_color(color)
                points_out_circle += 1
                self.add(point)
            pi_val = 4 * points_in_circle / (points_in_circle + points_out_circle)
            if not added_pi_value:
                dec = manim.DecimalNumber(pi_val, num_decimal_places=5, edge_to_fix=manim.RIGHT, font_size=72).to_corner(manim.UR)
                self.add(dec)
                added_pi_value = True
            else:
                dec.set_value(pi_val)
            self.wait(5 / self.camera.frame_rate)
        self.wait(2)
        if self.data is None:
            self.successful_data.append(
                {
                    "name": "pi_approximation_by_monte_carlo",
                    "args": {
                        "n_points_in_square": n_points_in_square,
                        "color_square": color_square,
                        "color_circle": color_circle,
                    },
                    "step": step,
                }
            )
            ResponseScene.select_template_history.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "pi_approximation_by_monte_carlo",
                                "response": {
                                    "name": "pi_approximation_by_monte_carlo",
                                    "content": f"""
The pi approximation by Monte Carlo method was shown successfully.

This is equivalent to the following custom template:

```python
import random
number_of_points = {n_points_in_square}
sq = Square(side_length=4).set_color({color_square})
circ = Circle(radius=2).set_color({color_circle})
self.play(Create(sq))
self.play(Create(circ))
self.wait(2)

added_pi_value = False
points_in_circle = 0
points_out_circle = 0

for _ in range(number_of_points):
    x = random.uniform(-2, 2)
    y = random.uniform(-2, 2)
    point = Dot(x * RIGHT + y * UP, radius=0.05)
    if (x ** 2 + y ** 2) <= 4:
        color = {color_circle}
        point.set_color(color)
        points_in_circle += 1
        self.add(point)
    else:
        color = {color_square}
        point.set_color(color)
        points_out_circle += 1
        self.add(point)
    pi_val = 4 * points_in_circle / (points_in_circle + points_out_circle)
    if not added_pi_value:
        dec = DecimalNumber(pi_val, num_decimal_places=5, edge_to_fix=RIGHT, font_size=72).to_corner(UR)
        self.add(dec)
        added_pi_value = True
    else:
        dec.set_value(pi_val)
    self.wait(5 / self.camera.frame_rate)
self.wait(2)
```
"""
                                }
                            }
                        }
                    ]
                }
            )

    def debug_custom_code(self, step: str, code: str, error: str) -> bool:
        self.clear()
        ResponseScene.debugger_history.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"""
Please debug the following code. The code is:
```python
{code}
```
And the error message is:
```
{error}
```

Remember the rules:
- Don't make the entire code, we're in the `construct` method, so just make the code that goes in there.
- Scene's variable is `self`, so use it directly.
- Don't import Manim, it's already imported.

Available methods and attributes for `self` are:
```
{dir(self)}
```

Available camera methods and attributes are:
```
{dir(self.camera)}
```

And available fonts for `Text` object are:
```
{list_fonts()}
```
"""
                    }
                ]
            }
        )
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
            params={
                "key": os.getenv("GOOGLE_API_KEY"),
            },
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": CUSTOM_CODE_DEBUGGER_INSTRUCTIONS,
                        },
                    ]
                },
                "contents": ResponseScene.debugger_history,
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "code": {
                                "type": "STRING",
                                "description": "Fixed code.",
                            },
                            "explanation": {
                                "type": "STRING",
                                "description": "Explanation of the error and the fix, with the changes you made.",
                            },
                        },
                        "required": ["code", "explanation"],
                    },
                }
            }
        )
        response_results = response.json()
        print(response_results)
        response.raise_for_status()
        response = json.loads(response_results["candidates"][0]["content"]["parts"][0]["text"])
        fixed_code = response["code"]
        print(f"Fixed code:\n{fixed_code}")
        explanation = response["explanation"]
        print(f"Explanation:\n{explanation}")
        ResponseScene.debugger_history.append(response_results["candidates"][0]["content"])
        try:
            scope = manim.__dict__.copy()
            scope["self"] = self
            scope["TitleAnimation"] = TitleAnimation
            scope["FunctionPlot"] = FunctionPlot
            scope["math"] = math
            exec(fixed_code, scope)
            ResponseScene.debugger_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
The code has been fixed, the successful code is:

```python
{fixed_code}
```
"""
                        }
                    ]
                }
            )
            if self.data is None:
                ResponseScene.select_template_history.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": "custom_template",
                                    "response": {
                                        "name": "custom_template",
                                        "content": f"""
    The code had errors, but has been fixed, the successful code is:

    ```python
    {fixed_code}
    ```
    """
                                    }
                                }
                            }
                        ]
                    }
                )
                self.successful_data.append(
                    {
                        "name": "custom_template",
                        "args": {
                            "code": fixed_code,
                        },
                        "step": step,
                    }
                )
            return True
        except TimeoutError as e:
            print("Timeout error")
            ResponseScene.debugger_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
The code was too heavy as to be executed. Your work for this scene has finished :(
"""
                        }
                    ]
                }
            )
            ResponseScene.select_template_history.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "custom_template",
                                "response": {
                                    "name": "custom_template",
                                    "content": f"""
It seems the code was too heavy as to be executed. Your work for this scene has finished :(
"""
                                }
                            }
                        }
                    ]
                }
            )
            self.successful_data.append(
                {
                    "name": "custom_template",
                    "args": {
                        "code": fixed_code,
                    },
                    "step": step,
                }
            )
            raise e
        except Exception as e:
            print(f"Error executing code: {e}")
            error_message = f"{type(e).__name__}: {e}"
            print(f"Error message: {error_message}")
            ResponseScene.debugger_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
Another error occurred while trying to execute. The new error message is:
```
{error_message}
```

Remember the original code was:
```python
{code}
```

And the code I executed was the same as you provided, which is:
```python
{fixed_code}
```

Remember the rules:
- Don't make the entire code, we're in the `construct` method, so just make the code that goes in there.
- Scene's variable is `self`, so use it directly.
- Don't import Manim, it's already imported.

Available methods and attributes for `self` are:
```
{dir(self)}
```

Available camera methods and attributes are:
```
{dir(self.camera)}
```

And available fonts for `Text` object are:
```
{list_fonts()}
```
"""
                        }
                    ]
                }
            )
        return False
 
    def show_step(self, step: str, index: int) -> None:
        step_title = text_to_latex(f"**Paso {index}**", 72)
        step_text = text_to_latex(step)
        self.arrange_objects([step_title, step_text], layout="vertical", buff=0.5)
        self.play(TitleAnimation(step_title))
        self.play(manim.AddTextLetterByLetter(step_text[0], run_time=2))
        self.wait(1)
        self.play(manim.FadeOut(step_text), step_title.animate.to_corner(manim.UL))

    def create_title(self, text: str) -> manim.Tex:
        """Create a title for the scene."""
        title = text_to_latex(f"**{text}**", font_size=72)
        return title
    
    def create_description(self, text: str) -> manim.Tex:
        """Create a description for the scene."""
        description = text_to_latex(text)
        return description

    def fade_out_scene(self) -> None:
        """Fade out all objects in the scene."""
        if len(self.mobjects) == 0:
            return
        self.play(manim.FadeOut(*self.mobjects))
        self.wait(1)
    
    def ensure_in_frame(self, mobject: manim.Mobject, padding: float = 1.0) -> manim.Mobject:
        """Ensure the object is within the frame."""
        # Scale the object to fit the frame if it's too large
        mobject = self.scale_to_fit_frame(mobject, padding)

        # Get the frame bounds
        x_min = -manim.config.frame_width / 2 + padding
        x_max = manim.config.frame_width / 2 - padding
        y_min = -manim.config.frame_height / 2 + padding
        y_max = manim.config.frame_height / 2 - padding

        # Use proper Manim methods to get the bounding box
        left = mobject.get_left()[0]
        right = mobject.get_right()[0]
        bottom = mobject.get_bottom()[1]
        top = mobject.get_top()[1]

        # Adjust if needed
        if left < x_min:  # Left boundary
            mobject.shift(manim.RIGHT * (x_min - left))
        if right > x_max:  # Right boundary
            mobject.shift(manim.LEFT * (right - x_max))
        if bottom < y_min:  # Bottom boundary
            mobject.shift(manim.UP * (y_min - bottom))
        if top > y_max:  # Top boundary
            mobject.shift(manim.DOWN * (top - y_max))

        return mobject

    def scale_to_fit_frame(self, obj: manim.Mobject, padding: float = 1.0) -> manim.Mobject:
        """Scale the object to fit the frame."""
        if obj.height > self.camera.frame_height - padding:
            obj.scale_to_fit_height(self.camera.frame_height - 1)
        if obj.width > self.camera.frame_width - padding:
            obj.scale_to_fit_width(self.camera.frame_width - 1)
        return obj
    
    def arrange_objects(self, objects: list[manim.Mobject], layout: str = "horizontal", buff: float = 0.5) -> None:
        """Arrange objects in the scene."""
        gr = manim.VGroup(*objects)
        if layout == "horizontal":
            gr.arrange(manim.RIGHT, buff=buff)
        elif layout == "vertical":
            gr.arrange(manim.DOWN, buff=buff)
        elif layout == "grid":
            # Calculate grid dimensions
            n = len(objects)
            cols = int(np.sqrt(n))
            rows = (n + cols - 1) // cols

            # Create grid arrangement
            grid = manim.VGroup()
            for i in range(rows):
                row_group = manim.VGroup()
                for j in range(cols):
                    idx = i * cols + j
                    if idx < n:
                        row_group.add(objects[idx])
                if len(row_group) > 0:
                    row_group.arrange(manim.RIGHT, buff=buff)
                    grid.add(row_group)
            grid.arrange(manim.DOWN, buff=buff)

            # Replace original group with grid arrangement
            for i, obj in enumerate(objects):
                if i < n:
                    objects[i].become(grid.submobjects[i // cols].submobjects[i % cols])
        else:
            raise ValueError("Invalid layout type. Use 'horizontal', 'vertical', or 'grid'.")
        return self.ensure_in_frame(gr)


class ResponseScene3D(manim.ThreeDScene, ResponseScene):
    """3D version of the ResponseScene."""
    pass


latex_history: list[dict[str, Any]] = []


def text_to_latex(text: str, font_size: int = 48) -> manim.Tex:
    """Convert text to LaTeX."""
    latex_history.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": f"""
Please convert the following text to LaTeX:

```
{text}
```

Don't make the entire document, just what's between the `\\begin{{document}}` and `\\end{{document}}` commands.
Also remember to NEVER put unicode characters in text mode representing math, like `²` or `³`. Always use LaTeX math mode for that. For example, if you have `x² + y² = z²`, you should write it as `$x^2 + y^2 = z^2$`.
"""
                }
            ]
        }
    )
    error = True
    while error:
        latex_response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
            params={
                "key": os.getenv("GOOGLE_API_KEY"),
            },
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": TEXT_TO_LATEX_INSTRUCTIONS,
                        },
                    ]
                },
                "contents": latex_history,
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "latex_code": {
                                "type": "STRING",
                                "description": "LaTeX code.",
                            }
                        },
                        "required": ["latex_code"],
                    },
                }
            }
        )
        latex_results = latex_response.json()
        print(latex_results)
        latex_response.raise_for_status()
        latex_response = json.loads(latex_results["candidates"][0]["content"]["parts"][0]["text"])
        latex_code = latex_response["latex_code"]
        print(f"Latex code:\n{latex_code}")
        latex_history.append(latex_results["candidates"][0]["content"])
        try:
            tex = manim.Tex(latex_code, font_size=font_size, color=manim.WHITE)
            error = False
        except Exception as e:
            print(f"Error creating LaTeX: {e}")
            error_message = f"{type(e).__name__}: {e}"
            print(f"Error message: {error_message}")
            latex_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
An error occurred while trying to create the LaTeX code. The error message is:

```
{error_message}
```

Fix it, but keep what's meant to be LaTeX code. Don't change the text, just fix the LaTeX code.
And don't make the entire document, just what's between the `\\begin{{document}}` and `\\end{{document}}` commands.
Also remember to NEVER put unicode characters in text mode representing math, like `²` or `³`. Always use LaTeX math mode for that. For example, if you have `x² + y² = z²`, you should write it as `$x^2 + y^2 = z^2$`.
"""
                        }
                    ]
                }
            )
            continue
    latex_history.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": f"""
The LaTeX code has been rendered, the successful code is:

```latex
{latex_code}
```
"""
                }
            ]
        }
    )
    return tex


coder_history: list[dict[str, Any]] = []


async def render_manim(message: discord.Message, title: str, description: str, is_3d: bool, steps: list[str] = [], considerations: list[str] = []) -> str:
    """Render the Manim scene."""
    manim.config.output_file = "ResponseScene"
    manim.config.format = "mp4"
    try:
        if not is_3d:
            scene = ResponseScene(title, description, steps, considerations)
            scene.render()
        else:
            scene = ResponseScene3D(title=title, description=description, steps=steps, considerations=considerations)
            scene.render()
        manim.config.output_file = "ResponseScene"
        manim.config.format = "mp4"
        if not is_3d:
            scene = ResponseScene(title, description, steps, considerations, scene.successful_data)
            scene.render()
        else:
            scene = ResponseScene3D(title=title, description=description, steps=steps, considerations=considerations, data=scene.successful_data)
            scene.render()
    except TimeoutError:
        return "TimeoutError: The request took more than the limit (2 minutes) to process. Please don't render too heavy scenes."
    manim.config.output_file = "ResponseScene"
    manim.config.format = "mp4"
    media_dir = pathlib.Path("media")
    file_path = media_dir / "videos" / "1080p60" / "ResponseScene.mp4"
    if not file_path.exists():
        return "Rendered file not found. Please try again."
    with open(file_path, "rb") as f:
        video_file = discord.File(f, "ResponseScene.mp4")
    if isinstance(message.channel, discord.DMChannel):
        await message.author.send(file=video_file, reference=message)
    else:
        await message.channel.send(file=video_file, reference=message)
    return "It has been rendered succesfully"

debugger_history: list[dict[str, Any]] = []


def math_problem_state(problem: str) -> str:
    """Return the state of the math problem."""
    problem_state_response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
        params={
            "key": os.getenv("GOOGLE_API_KEY"),
        },
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {
                "parts": [
                    {
                        "text": PROBLEM_STATE_INSTRUCTIONS,
                    },
                ]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": problem,
                        },
                    ],
                    "role": "user",
                },
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "problem_state": {
                            "type": "STRING",
                            "description": "State of the math problem.",
                        }
                    },
                    "required": ["problem_state"],
                },
            }
        }
    )
    problem_state_results = problem_state_response.json()
    print(problem_state_results)
    problem_state_response.raise_for_status()
    problem_state_response = json.loads(problem_state_results["candidates"][0]["content"]["parts"][0]["text"])
    problem_state = problem_state_response["problem_state"]
    return problem_state


solve_math_history: list[dict[str, Any]] = []


def solve_math(problem_statement: str) -> dict[str, Any]:
    """Solve the math problem."""
    solve_math_history.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": problem_statement,
                },
            ],
        }
    )
    there_was_function_call: bool = True
    while there_was_function_call:
        function_response: dict[str, Any] | None = None
        problem_response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
            params={
                "key": os.getenv("GOOGLE_API_KEY"),
            },
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": MATH_SOLVE_INSTRUCTIONS,
                        },
                    ]
                },
                "contents": solve_math_history,
                "tools": [
                    {
                        "functionDeclarations": [
                            {
                                "name": "sympy_calculator",
                                "description": "Use SymPy to calculate arithmetic, algebraic or derivatives/integrals stuff.",
                                "parameters": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "python_expr_to_evaluate": {
                                            "type": "STRING",
                                            "description": "A Python expression to evaluate with `eval`. SymPy is already in the scope as `sympy`, so no need to import it. Also it should be a string.",
                                        },
                                    },
                                    "required": ["python_expr_to_evaluate"],
                                },
                            }
                        ]
                    }
                ]
            },
        )
        problem_results = problem_response.json()
        print(problem_results)
        problem_response.raise_for_status()
        content = problem_results["candidates"][0]["content"]
        parts = content["parts"]
        solve_math_history.append(content)
        for part in parts:
            if "functionCall" in part:
                if function_response is None:
                    function_response = {
                        "role": "function",
                        "parts": []
                    }
                name = part["functionCall"]["name"]
                args = part["functionCall"]["args"]
                try:
                    expr = eval(args["python_expr_to_evaluate"], {"sympy": sympy})
                    result = str(expr)
                except Exception as e:
                    result = fix_code_errors(args["python_expr_to_evaluate"], f"{type(e).__name__}: {e}")
                print(f"Result: {result}")
                function_response["parts"].append(
                    {
                        "functionResponse": {
                            "name": name,
                            "response": {
                                "name": name,
                                "content": result,
                            }
                        }
                    }
                )
            if "text" in part:
                text = part["text"]
                print(f"Text: {text}")
        
        if function_response is not None:
            solve_math_history.append(function_response)
        there_was_function_call = function_response is not None
    return {
        "solved_problem": text
    }


code_fix_history: list[dict[str, Any]] = []


def fix_code_errors(code: str, error: str) -> str:
    """Fix code errors."""
    code_fix_history.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": f"""
Please fix the errors in this Python code.

```python
{code}
```

This is the error message:
```
{error}
```
"""
                }
            ],
        }
    )
    for _ in range(5):
        code_fix_response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
            params={
                "key": os.getenv("GOOGLE_API_KEY"),
            },
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": CODE_FIXER_INSTRUCTIONS,
                        },
                    ]
                },
                "contents": code_fix_history,
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "code": {
                                "type": "STRING",
                                "description": "Fixed code.",
                            },
                            "explanation": {
                                "type": "STRING",
                                "description": "Explanation of the error and the fix, with the changes you made.",
                            },
                        },
                        "required": ["code", "explanation"],
                    },
                }
            }
        )
        code_fix_results = code_fix_response.json()
        print(code_fix_results)
        code_fix_response.raise_for_status()
        code_fix_response = json.loads(code_fix_results["candidates"][0]["content"]["parts"][0]["text"])
        fixed_code = code_fix_response["code"]
        print(f"Fixed code:\n{fixed_code}")
        explanation = code_fix_response["explanation"]
        print(f"Explanation:\n{explanation}")
        code_fix_history.append(code_fix_results["candidates"][0]["content"])
        try:
            result = eval(fixed_code)
            result = str(result)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error executing code: {e}")
            error_message = f"{type(e).__name__}: {e}"
            print(f"Error message: {error_message}")
            code_fix_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
Another error occurred while trying to execute. The new error message is:

```
{error_message}
```

Remember the original code was:

```python
{code}
```

And the code I executed was the same as you provided, which is:
```python
{fixed_code}
```

Remember the rules:
- Imports will lead to an error, so don't use them. `sympy` is already in the scope so you can use it directly (e.g. `sympy.sin(x)`).
- Never import anything, nor `sympy` nor anything else.

Please fix the errors in this Python code.
"""
                        }
                    ]
                }
            )
            continue
        else:
            code_fix_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"""
The code has been fixed, the fixed code is:

```python
{fixed_code}
```
"""
                        }
                    ]
                }
            )
            return result
    return "An error occurred while executing the code."
