from discord.ext import commands
import discord
import json
from io import StringIO
import time
from typing import Any

from .utils import attachment_parts, render_tex
from .tools import render_manim, solve_math, bing_search
from .instructions import ACADEMIC_INSTRUCTIONS
from .regex import tex_message
from .locks import ai_lock
from .client import client


class AI(commands.Cog):
    current_input: list[dict[str, Any]] = []
    previous_response_id: str | None = None

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
        if after.author == self.bot.user:
            return
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
                    "previous_message": before.content,
                },
                io,
                ensure_ascii=False,
                indent=4,
            )
            io.seek(0)
            self.current_input.append(
                {
                    "type": "input_text",
                    "text": io.getvalue(),
                }
            )
            self.current_input.extend(await attachment_parts(after.attachments))
            if self.bot.user.mentioned_in(after) or isinstance(after.channel, discord.DMChannel):
                user_input = {
                    "role": "user",
                    "content": self.current_input.copy(),
                }
                there_was_function_call: bool = True
                self.current_input.clear()
                while there_was_function_call:
                    there_was_function_call = False
                    response = client.responses.create(
                        model="gpt-4o",
                        input=user_input,
                        instructions=ACADEMIC_INSTRUCTIONS,
                        temperature=0.0,
                        previous_response_id=self.previous_response_id,
                        tools=[
                            {
                                "type": "function",
                                "name": "bing_search",
                                "description": "Search the internet.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "The search query.",
                                        },
                                    },
                                    "required": ["query"],
                                    "additionalProperties": False,
                                }
                            },
                            {
                                "type": "function",
                                "name": "render_manim",
                                "description": "Render a Manim animation.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string",
                                            "description": "The title of the animation.",
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "The description of the animation. It's all what should be shown in the rendered video.",
                                        },
                                        "is_3d": {
                                            "type": "boolean",
                                            "description": "Whether the scene is 3D or not.",
                                        },
                                    },
                                    "required": ["title", "description", "is_3d"],
                                    "additionalProperties": False,
                                }
                            },
                            {
                                "type": "function",
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
                                    "additionalProperties": False,
                                }
                            }
                        ]
                    )
                    output = response.output
                    self.previous_response_id = response.id
                    user_input = []
                    for out in output:
                        if not isinstance(out, dict):
                            out = out.to_dict(mode="json")
                        if out.get("type") == "function_call":
                            there_was_function_call = True
                            name = content.get("name")
                            arguments = json.loads(out.get("arguments"))
                            if name == "render_manim":
                                result = await render_manim(after, **arguments)
                            elif name == "bing_search":
                                result = bing_search(**arguments)
                            elif name == "solve_math":
                                result = solve_math(**arguments)
                            user_input.append({
                                "type": "function_call_output",
                                "call_id": out.get("call_id"),
                                "output": str(result)
                            })
                        contents = out.get("content")
                        if contents:
                            for content in contents:
                                if content.get("type") == "output_text":
                                    for i in range(0, len(content.get("text")), 2000):
                                        await after.reply(content=content.get("text")[i:i + 2000])
                                    if tex_message.search(content.get("text")):
                                        await render_tex(after, content.get("text"))
                    time.sleep(1.0)  # Avoid rate limit

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return
        async with ai_lock:
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
                    "previous_message": None
                },
                io,
                ensure_ascii=False,
                indent=4,
            )
            io.seek(0)
            self.current_input.append(
                {
                    "type": "input_text",
                    "text": io.getvalue(),
                }
            )
            self.current_input.extend(await attachment_parts(message.attachments))
            if self.bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
                user_input = [{
                    "role": "user",
                    "content": self.current_input.copy(),
                }]
                there_was_function_call: bool = True
                self.current_input.clear()
                while there_was_function_call:
                    there_was_function_call = False
                    response = client.responses.create(
                        model="gpt-4o",
                        input=user_input,
                        instructions=ACADEMIC_INSTRUCTIONS,
                        temperature=0.0,
                        previous_response_id=self.previous_response_id,
                        tools=[
                            {
                                "type": "function",
                                "name": "bing_search",
                                "description": "Search the internet.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "The search query.",
                                        },
                                    },
                                    "required": ["query"],
                                    "additionalProperties": False,
                                },
                            },
                            {
                                "type": "function",
                                "name": "render_manim",
                                "description": "Render a Manim animation.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string",
                                            "description": "The title of the animation.",
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "The description of the animation. It's all what should be shown in the rendered video.",
                                        },
                                        "is_3d": {
                                            "type": "boolean",
                                            "description": "Whether the scene is 3D or not.",
                                        },
                                    },
                                    "additionalProperties": False,
                                    "required": ["title", "description", "is_3d"],
                                }
                            },
                            {
                                "type": "function",
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
                                    "additionalProperties": False,
                                    "required": ["problem_statement"],
                                }
                            }
                        ]
                    )
                    output = response.output
                    self.previous_response_id = response.id
                    user_input = []
                    for out in output:
                        if not isinstance(out, dict):
                            out = out.to_dict(mode="json")
                        if out.get("type") == "function_call":
                            there_was_function_call = True
                            name = out.get("name")
                            arguments = json.loads(out.get("arguments"))
                            if name == "render_manim":
                                time.sleep(1.0)  # Avoid rate limit
                                result = await render_manim(message, **arguments)
                            elif name == "bing_search":
                                time.sleep(1.0)  # Avoid rate limit
                                result = bing_search(**arguments)
                            elif name == "solve_math":
                                time.sleep(1.0)  # Avoid rate limit
                                result = solve_math(**arguments)
                            user_input.append({
                                "type": "function_call_output",
                                "call_id": out.get("call_id"),
                                "output": str(result)
                            })
                        contents = out.get("content")
                        if contents:
                            for content in contents:
                                if content.get("type") == "output_text":
                                    for i in range(0, len(content.get("text")), 2000):
                                        await message.reply(content=content.get("text")[i:i + 2000])
                                    if tex_message.search(content.get("text")):
                                        await render_tex(message, content.get("text"))
                    time.sleep(1.0)  # Avoid rate limit
