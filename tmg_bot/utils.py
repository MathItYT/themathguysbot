import discord
import emoji
import pathlib
import subprocess
import base64
import os
from io import StringIO
import json
import requests
from typing import Any
import manim
import numpy as np
import sympy

from .tex_templates import DEFAULT_TEX_TEMPLATE
from .instructions import (
    PLANNER_INSTRUCTIONS,
    CODER_INSTRUCTIONS,
    DEBUGGER_INSTRUCTIONS,
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


async def render_tex(message: discord.Message) -> None:
    temp_dir: pathlib.Path = pathlib.Path("temp")
    md = fix_tex_bugs(message.content)
    channel = message.channel
    temp_tex = temp_dir / f"{message.id}.tex"
    temp_png = temp_dir / f"{message.id}.png"
    temp_tex.write_text(DEFAULT_TEX_TEMPLATE.format(md=md), encoding="utf-8")
    try:
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


def plan_manim_scene(context: str) -> dict[str, Any]:
    """Plan the manim scene using the context."""
    history = [
        {
            "text": context,
        }
    ]
    plan_response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={
            "key": os.getenv("GOOGLE_API_KEY"),
        },
        headers={"Content-Type": "application/json"},
        json={
            "contents": [
                {
                    "parts": history,
                    "role": "user",
                },
            ],
            "system_instruction": {
                "parts": [
                    {
                        "text": PLANNER_INSTRUCTIONS,
                    },
                ]
            },
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {
                            "type": "STRING",
                            "description": "Scene class name, must be a valid Python class name.",
                        },
                        "description": {
                            "type": "STRING",
                            "description": "Scene description.",
                        },
                        "steps": {
                            "type": "ARRAY",
                            "items": {
                                "type": "STRING",
                                "description": "Step to follow.",
                            },
                            "description": "Clear and concise steps outlining the actions to be taken in the scene.",
                        },
                    },
                    "required": ["title", "description", "steps"],
                }
            },
        }
    )
    plan_results = plan_response.json()
    print(plan_results)
    plan_response.raise_for_status()
    return json.loads(plan_results["candidates"][0]["content"]["parts"][0]["text"])


full_code: str = """
{code}

config.tex_template = TexTemplate(
    preamble=r\"\"\"
    \\usepackage[spanish]{{babel}}
    \\usepackage{{amsmath}}
    \\usepackage{{amssymb}}
    \\usepackage{{xcolor}}
    \\usepackage{{mlmodern}}
    \"\"\"
)
config.background_color = "#161616"
config.disable_caching = True
config.output_file = "{scene_class_name}"

scene = {scene_class_name}()
scene.render()
"""


class ResponseScene(manim.Scene):
    """Scene class for rendering responses."""

    def create_title(self, text: str) -> manim.Tex:
        """Create a title for the scene."""
        title = manim.Tex(r"\textbf{" + text + "}", font_size=72, color=manim.WHITE)
        self.ensure_in_frame(title)
        return title
    
    def fade_out_scene(self) -> None:
        """Fade out all objects in the scene."""
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
            gr.arrange(manim.UP, buff=buff)
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


coder_history: list[dict[str, Any]] = []


async def render_manim(message: discord.Message, scene_class_name: str, description: str, steps: list[str] = [], considerations: list[str] = []) -> tuple[bool, str | None, str | None]:
    """Render the Manim scene."""
    io = StringIO()
    json.dump(
        {
            "scene_class_name": scene_class_name,
            "description": description,
            "steps": steps,
            "considerations": considerations,
        },
        io,
    )
    io.seek(0)
    coder_history.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": io.read(),
                },
            ]
        }
    )
    coder_response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={
            "key": os.getenv("GOOGLE_API_KEY"),
        },
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {
                "parts": [
                    {
                        "text": CODER_INSTRUCTIONS,
                    },
                ]
            },
            "contents": coder_history,
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "code": {
                            "type": "STRING",
                            "description": "Code for the Manim scene.",
                        }
                    },
                    "required": ["code"],
                },
            }
        }
    )
    coder_results = coder_response.json()
    coder_response.raise_for_status()
    coder_response = json.loads(coder_results["candidates"][0]["content"]["parts"][0]["text"])
    content = coder_results["candidates"][0]["content"]
    coder_history.append(content)
    code = coder_response["code"]
    try:
        ctx = manim.__dict__
        ctx["ResponseScene"] = ResponseScene
        exec(full_code.format(code=code, scene_class_name=scene_class_name), ctx)
    except Exception as e:
        print(full_code.format(code=code, scene_class_name=scene_class_name))
        print(f"Error rendering Manim scene: {e}")
        return await fix_manim_errors(message, code, scene_class_name, e)
    else:
        video_path: pathlib.Path = pathlib.Path("media/videos/1080p60/")
        video_path = video_path / f"{scene_class_name}.mp4"
        image_path: pathlib.Path = pathlib.Path("media/images/")
        image_path = image_path / f"{scene_class_name}_ManimCE_v0.19.0.png"
        if not video_path.exists() and not image_path.exists():
            return await fix_manim_errors(message, code, scene_class_name, f"Output file not found with class name {scene_class_name}.")
        with open(video_path if video_path.exists() else image_path, "rb") as f:
            if isinstance(message.channel, discord.DMChannel):
                await message.author.send(file=discord.File(f, "manim_scene.mp4"), reference=message)
            else:
                await message.channel.send(file=discord.File(f, "manim_scene.mp4"), reference=message)
        with open(video_path if video_path.exists() else image_path, "rb") as f:
            b64_video_or_image = base64.b64encode(f.read()).decode("utf-8")
        coder_history.append(
            {
                "role": "user",
                "parts": [{
                    "text": "Your code was successfully rendered.",
                }]
            }
        )
        mime_type = "video/mp4" if video_path.exists() else "image/png"
        return True, b64_video_or_image, mime_type


debugger_history: list[dict[str, Any]] = []


async def fix_manim_errors(message: discord.Message, code: str, scene_class_name: str, error: Exception) -> tuple[bool, str | None, str | None]:
    """Fix Manim errors."""
    error_message = f"{type(error).__name__}: {error}"
    parts = [
        {
            "text": f"""
    Please fix the errors in this Manim code.


    CODE WITH ERRORS:
    ```python
    {code}
    ```

    ERROR MESSAGE:
    ```
    {error_message}
    ```

    Please provide a complete fixed version of the code, along with an explanation of what went wrong and how you fixed it, and also keep the class name of the scene as {scene_class_name}.
    Also keep the same inheritance of the scene class, and the same methods and attributes as the original code.
    """
        },
    ]
    debugger_history.append(
        {
            "parts": parts,
            "role": "user",
        }
    )
    for _ in range(5):
        debugger_response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            params={
                "key": os.getenv("GOOGLE_API_KEY"),
            },
            headers={"Content-Type": "application/json"},
            json={
                "system_instruction": {
                    "parts": [
                        {
                            "text": DEBUGGER_INSTRUCTIONS,
                        },
                    ]
                },
                "contents": debugger_history,
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "OBJECT",
                        "properties": {
                            "code": {
                                "type": "STRING",
                                "description": "Fixed code for the Manim scene.",
                            },
                            "explanation": {
                                "type": "STRING",
                                "description": "Explanation of the error and the fix.",
                            },
                            "changes": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "STRING",
                                    "description": "Changes made to the code.",
                                },
                                "description": "List of changes made to the code.",
                            },
                        },
                        "required": ["code", "explanation", "changes"],
                    },
                }
            }
        )
        debugger_results = debugger_response.json()
        debugger_response.raise_for_status()
        debugger_response = json.loads(debugger_results["candidates"][0]["content"]["parts"][0]["text"])
        code = debugger_response["code"]
        explanation = debugger_response["explanation"]
        changes = '\n'.join(debugger_response["changes"])
        print(f"Fixed code:\n{code}")
        print(f"Explanation:\n{explanation}")
        print(f"Changes:\n{changes}")
        debugger_history.append(debugger_results["candidates"][0]["content"])
        try:
            ctx = manim.__dict__
            ctx["ResponseScene"] = ResponseScene
            exec(full_code.format(code=code, scene_class_name=scene_class_name), ctx)
        except Exception as e:
            print(f"Error rendering Manim scene: {e}")
            error_message = f"{type(e).__name__}: {e}"
            print(f"Error message: {error_message}")
            debugger_history.append(
                {
                    "role": "user",
                    "parts": [
                        {
                    "text": f"""
Another error occurred while trying to render the fixed code. The new error message is:

```
{error_message}
```
Please fix the errors in this Manim code.
""",
                        }
                    ]
                }
            )
            continue
        else:
            video_path: pathlib.Path = pathlib.Path("media/videos/1080p60/")
            video_path = video_path / f"{scene_class_name}.mp4"
            image_path: pathlib.Path = pathlib.Path("media/images/")
            image_path = image_path / f"{scene_class_name}_ManimCE_v0.19.0.png"
            if not video_path.exists() and not image_path.exists():
                error_message = f"Output file not found with class name {scene_class_name}."
                continue
            with open(video_path if video_path.exists() else image_path, "rb") as f:
                if isinstance(message.channel, discord.DMChannel):
                    await message.author.send(file=discord.File(f, "manim_scene.mp4"), reference=message)
                else:
                    await message.channel.send(file=discord.File(f, "manim_scene.mp4"), reference=message)
            coder_history.append(
                {
                    "role": "user",
                    "parts": [{
                        "text": f"""The code had errors, the fixed code is:

```python
{code}
```
"""
                    }]
                }
            )
            with open(video_path if video_path.exists() else image_path, "rb") as f:
                b64_video_or_image = base64.b64encode(f.read()).decode("utf-8")
            mime_type = "video/mp4" if video_path.exists() else "image/png"
            return True, b64_video_or_image, mime_type
    return False, None, None


def math_problem_state(problem: str) -> str:
    """Return the state of the math problem."""
    problem_state_response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
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
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
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
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
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
