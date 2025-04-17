from discord.ext import commands
import discord
import requests
import json
from io import StringIO
import os
from typing import Any

from .utils import attachment_parts, render_tex, internet_search, render_manim, math_problem_state, solve_math
from .instructions import ACADEMIC_INSTRUCTIONS
from .regex import tex_message
from .locks import ai_lock


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class AI(commands.Cog):
    history: list = []

    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print("Bot is ready")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        general_id = 1045453709221568535
        rules_id = 1046564924035436674
        aplus_id = 1196603434254737468
        general: discord.TextChannel | None = self.bot.get_channel(general_id)
        rules: discord.TextChannel | None = self.bot.get_channel(rules_id)
        aplus: discord.Emoji | None = self.bot.get_emoji(aplus_id)
        if general is not None and rules is not None and aplus is not None:
            await general.send(f"¡Bienvenido {member.mention} a The Math Guys! Recuerda leer todas las reglas en {rules.mention} y verificarte ahí mismo. ¡Disfruta tu estadía! {aplus}")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        async with ai_lock:
            io = StringIO()
            json.dump(
                {
                    "message": after.content,
                    "user_ping": after.author.mention,
                    "user_name": after.author.name,
                    "channel": after.channel.name if not isinstance(after.channel, discord.DMChannel) else "DM Channel",
                    "channel_mention": after.channel.mention if not isinstance(after.channel, discord.DMChannel) else after.author.mention,
                    "time_utc": after.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "replying_to_user_with_ping": after.reference.resolved.author.mention if after.reference and isinstance(after.reference.resolved, discord.Message) else None,
                },
                io,
                ensure_ascii=False,
                indent=4,
            )
            io.seek(0)
            user_input = [
                {
                    "text": io.read(),
                }
            ]
            user_input.extend(await attachment_parts(after.attachments))
            AI.history.append({
                "role": "user",
                "parts": user_input,
            })
            if self.bot.user.mentioned_in(after) or isinstance(after.channel, discord.DMChannel):
                there_was_function_call: bool = True
                while there_was_function_call:
                    function_response: dict[str, Any] | None = None
                    response = requests.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
                        params={"key": GOOGLE_API_KEY},
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": AI.history,
                            "system_instruction": {
                                "parts": [
                                    {
                                        "text": ACADEMIC_INSTRUCTIONS,
                                    }
                                ]
                            },
                            "tools": [
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "internet_search",
                                            "description": "Search the internet for information.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "query": {
                                                        "type": "string",
                                                        "description": "The search query.",
                                                    },
                                                },
                                                "required": ["query"],
                                            },
                                        }
                                    ],
                                },
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "render_manim",
                                            "description": "Internally it creates a code for a Manim scene and renders it.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {
                                                        "type": "string",
                                                        "description": "The scene's title.",
                                                    },
                                                    "description": {
                                                        "type": "string",
                                                        "description": "The description for the scene.",
                                                    },
                                                    "steps": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string",
                                                            "description": "The steps to follow.",
                                                        },
                                                        "description": "Clear and concise steps outlining the actions to be taken in the scene.",
                                                    },
                                                    "considerations": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string",
                                                            "description": "User will let you know some considerations, you must take them into account.",
                                                        },
                                                        "description": "Considerations for the scene.",
                                                    },
                                                    "is_3d": {
                                                        "type": "boolean",
                                                        "description": "Whether the scene is 3D or not.",
                                                    },
                                                },
                                                "required": ["title", "description", "steps", "considerations", "is_3d"],
                                            },
                                        }
                                    ],
                                },
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "math_problem_state",
                                            "description": "State the math problem in a way the math solver can understand.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "problem": {
                                                        "type": "string",
                                                        "description": "The math problem in user's words.",
                                                    },
                                                },
                                                "required": ["problem"],
                                            },
                                        },
                                        {
                                            "name": "solve_math",
                                            "description": "Solve a math problem.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "problem_statement": {
                                                        "type": "string",
                                                        "description": "The math problem statement.",
                                                    },
                                                },
                                                "required": ["problem_statement"],
                                            },
                                        }
                                    ]
                                }
                            ],
                        }
                    )
                    response_json = response.json()
                    print(response_json)
                    try:
                        response.raise_for_status()
                    except requests.exceptions.HTTPError as e:
                        AI.history.clear()
                    candidate = response_json["candidates"][0]
                    content = candidate["content"]
                    parts = content["parts"]
                    AI.history.append(content)
                    for part in parts:
                        if "text" in part:
                            if len(part["text"]) > 0:
                                if isinstance(after.channel, discord.DMChannel):   
                                    for i in range(0, len(part["text"]), 2000):
                                        await after.author.send(part["text"][i:i+2000], reference=after)
                                else:
                                    for i in range(0, len(part["text"]), 2000):
                                        await after.channel.send(part["text"][i:i+2000], reference=after)
                                if tex_message.search(part["text"]):
                                    await render_tex(after, part["text"])
                        if "functionCall" in part:
                            if function_response is None:
                                function_response = {
                                    "role": "function",
                                    "parts": []
                                }
                            name = part["functionCall"]["name"]
                            args = part["functionCall"]["args"]
                            if name == "internet_search":
                                output = internet_search(**args)
                                function_response["parts"].append({
                                    "functionResponse": {
                                        "name": name,
                                        "response": {
                                            "name": name,
                                            "content": output,
                                        }
                                    }
                                })
                            elif name == "render_manim":
                                err_or_suc_msg = await render_manim(after, **args)
                                function_response["parts"].append({
                                    "functionResponse": {
                                        "name": name,
                                        "response": {
                                            "name": name,
                                            "content": err_or_suc_msg
                                        }
                                    }
                                })
                            elif name == "math_problem_state":
                                output = math_problem_state(**args)
                                function_response["parts"].append(
                                    {
                                        "functionResponse": {
                                            "name": name,
                                            "response": {
                                                "name": name,
                                                "content": output,
                                            }
                                        }
                                    }
                                )
                            elif name == "solve_math":
                                output = solve_math(**args)
                                AI.history.append(
                                    {
                                        "functionResponse": {
                                            "name": name,
                                            "response": {
                                                "name": name,
                                                "content": output,
                                            }
                                        }
                                    }
                                )
                            AI.history.append(function_response)
                                
                    there_was_function_call = function_response is not None


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        async with ai_lock:
            if message.author == self.bot.user:
                return
            io = StringIO()
            json.dump(
                {
                    "message": message.content,
                    "user_ping": message.author.mention,
                    "user_name": message.author.name,
                    "channel": message.channel.name if not isinstance(message.channel, discord.DMChannel) else "DM Channel",
                    "channel_mention": message.channel.mention if not isinstance(message.channel, discord.DMChannel) else message.author.mention,
                    "time_utc": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "replying_to_user_with_ping": message.reference.resolved.author.mention if message.reference and isinstance(message.reference.resolved, discord.Message) else None,
                },
                io,
                ensure_ascii=False,
                indent=4,
            )
            io.seek(0)
            user_input = [
                {
                    "text": io.read(),
                }
            ]
            user_input.extend(await attachment_parts(message.attachments))
            AI.history.append({
                "role": "user",
                "parts": user_input,
            })
            if self.bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
                there_was_function_call: bool = True
                while there_was_function_call:
                    function_response: dict[str, Any] | None = None
                    response = requests.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
                        params={"key": GOOGLE_API_KEY},
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": AI.history,
                            "system_instruction": {
                                "parts": [
                                    {
                                        "text": ACADEMIC_INSTRUCTIONS,
                                    }
                                ]
                            },
                            "tools": [
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "internet_search",
                                            "description": "Search the internet for information.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "query": {
                                                        "type": "string",
                                                        "description": "The search query.",
                                                    },
                                                },
                                                "required": ["query"],
                                            },
                                        }
                                    ],
                                },
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "render_manim",
                                            "description": "Internally it creates a code for a Manim scene and renders it.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {
                                                        "type": "string",
                                                        "description": "The scene's title.",
                                                    },
                                                    "description": {
                                                        "type": "string",
                                                        "description": "The description for the scene.",
                                                    },
                                                    "steps": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string",
                                                            "description": "The steps to follow.",
                                                        },
                                                        "description": "Clear and concise steps outlining the actions to be taken in the scene.",
                                                    },
                                                    "considerations": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string",
                                                            "description": "User will let you know some considerations, you must take them into account.",
                                                        },
                                                        "description": "Considerations for the scene.",
                                                    },
                                                    "is_3d": {
                                                        "type": "boolean",
                                                        "description": "Whether the scene is 3D or not.",
                                                    },
                                                },
                                                "required": ["title", "description", "steps", "considerations", "is_3d"],
                                            },
                                        }
                                    ],
                                },
                                {
                                    "functionDeclarations": [
                                        {
                                            "name": "math_problem_state",
                                            "description": "State the math problem in a way the math solver can understand.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "problem": {
                                                        "type": "string",
                                                        "description": "The math problem in user's words.",
                                                    },
                                                },
                                                "required": ["problem"],
                                            },
                                        },
                                        {
                                            "name": "solve_math",
                                            "description": "Solve a math problem.",
                                            "parameters": {
                                                "type": "object",
                                                "properties": {
                                                    "problem_statement": {
                                                        "type": "string",
                                                        "description": "The math problem statement.",
                                                    },
                                                },
                                                "required": ["problem_statement"],
                                            },
                                        }
                                    ]
                                }
                            ],
                        }
                    )
                    response_json = response.json()
                    print(response_json)
                    try:
                        response.raise_for_status()
                    except requests.exceptions.HTTPError as e:
                        AI.history.clear()
                    candidate = response_json["candidates"][0]
                    content = candidate["content"]
                    parts = content["parts"]
                    AI.history.append(content)
                    for part in parts:
                        if "text" in part:
                            if len(part["text"]) > 0:
                                if isinstance(message.channel, discord.DMChannel):
                                    for i in range(0, len(part["text"]), 2000):
                                        if len(part["text"][i:i+2000].strip()) > 0:
                                            await message.author.send(part["text"][i:i+2000], reference=message)
                                else:
                                    for i in range(0, len(part["text"]), 2000):
                                        if len(part["text"][i:i+2000].strip()) > 0:
                                            await message.channel.send(part["text"][i:i+2000], reference=message)
                                if tex_message.search(part["text"]):
                                    await render_tex(message, part["text"])
                        if "functionCall" in part:
                            if function_response is None:
                                function_response = {
                                    "role": "function",
                                    "parts": []
                                }
                            name = part["functionCall"]["name"]
                            args = part["functionCall"]["args"]
                            if name == "internet_search":
                                output = internet_search(**args)
                                function_response["parts"].append({
                                    "functionResponse": {
                                        "name": name,
                                        "response": {
                                            "name": name,
                                            "content": output,
                                        }
                                    }
                                })
                            elif name == "render_manim":
                                err_or_suc_msg = await render_manim(message, **args)
                                function_response["parts"].append({
                                    "functionResponse": {
                                        "name": name,
                                        "response": {
                                            "name": name,
                                            "content": err_or_suc_msg
                                        }
                                    }
                                })
                            elif name == "math_problem_state":
                                output = math_problem_state(**args)
                                function_response["parts"].append(
                                    {
                                        "functionResponse": {
                                            "name": name,
                                            "response": {
                                                "name": name,
                                                "content": output,
                                            }
                                        }
                                    }
                                )
                            elif name == "solve_math":
                                output = solve_math(**args)
                                function_response["parts"].append(
                                    {
                                        "functionResponse": {
                                            "name": name,
                                            "response": {
                                                "name": name,
                                                "content": output,
                                            }
                                        }
                                    }
                                )
                    if function_response is not None:
                        AI.history.append(function_response)
                    there_was_function_call = function_response is not None
