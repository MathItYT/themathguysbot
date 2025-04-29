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
from .supabase_client import supabase


mecenas: int = 1357139735700574218
message_limit: int = 500


class AI(commands.Cog):
    current_input: list[dict[str, Any]] = []
    previous_response_id: str | None = None
    message_count: int = 0

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
    
    # Reaction
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        msg = await channel.fetch_message(payload.message_id)
        if msg is None:
            return
        reaction = discord.utils.get(msg.reactions, emoji=payload.emoji.name)
        if reaction is None:
            return
        user = self.bot.get_user(payload.user_id)
        if user is None:
            return
        msg_in_supabase = supabase.table("videos_dataset").select("*").eq("id", str(msg.id)).execute()
        # Checks if user reacted to the message in Discord
        if msg_in_supabase.data:
            positive_reaction = [r for r in msg.reactions if r.emoji == "👍"][0]
            negative_reaction = [r for r in msg.reactions if r.emoji == "👎"][0]
            if reaction.emoji in ["👍", "👎"]:
                async for u in positive_reaction.users():
                    if u == user and reaction.emoji == "👎":
                        await positive_reaction.remove(user)
                async for u in negative_reaction.users():
                    if u == user and reaction.emoji == "👍":
                        await negative_reaction.remove(user)
                await msg.reply(f"¡Gracias por tu feedback {user.mention}!")
                # Fetch message again to get the updated reaction counts
                msg = await channel.fetch_message(payload.message_id)
                if msg is None:
                    return
                positive_reaction = [r for r in msg.reactions if r.emoji == "👍"][0]
                negative_reaction = [r for r in msg.reactions if r.emoji == "👎"][0]
                positive_votes = positive_reaction.count - 1
                negative_votes = negative_reaction.count - 1
                total_votes = positive_votes + negative_votes
                feedback = positive_votes / total_votes if total_votes > 0 else None
                supabase.table("videos_dataset").update({"positive_votes": positive_votes, "total_votes": total_votes, "feedback": feedback}).eq("id", str(msg.id)).execute()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        msg = await channel.fetch_message(payload.message_id)
        if msg is None:
            return
        reaction = discord.utils.get(msg.reactions, emoji=payload.emoji.name)
        if reaction is None:
            return
        user = self.bot.get_user(payload.user_id)
        if user is None:
            return
        msg_in_supabase = supabase.table("videos_dataset").select("*").eq("id", str(msg.id)).execute()
        if msg_in_supabase.data:
            positive_reaction = [r for r in msg.reactions if r.emoji == "👍"][0]
            negative_reaction = [r for r in msg.reactions if r.emoji == "👎"][0]
            if reaction.emoji in ["👍", "👎"]:
                # Fetch message again to get the updated reaction counts
                msg = await channel.fetch_message(payload.message_id)
                if msg is None:
                    return
                positive_reaction = [r for r in msg.reactions if r.emoji == "👍"][0]
                negative_reaction = [r for r in msg.reactions if r.emoji == "👎"][0]
                positive_votes = positive_reaction.count - 1
                negative_votes = negative_reaction.count - 1
                total_votes = positive_votes + negative_votes
                feedback = positive_votes / total_votes if total_votes > 0 else None
                supabase.table("videos_dataset").update({"positive_votes": positive_votes, "total_votes": total_votes, "feedback": feedback}).eq("id", str(msg.id)).execute()

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.author == self.bot.user:
            return
        if isinstance(after.channel, discord.DMChannel):
            rol_mecenas = discord.utils.get(self.bot.guilds[0].roles, id=mecenas)
            guild_member = discord.utils.get(self.bot.guilds[0].members, id=after.author.id)
            if guild_member is None:
                await after.reply(
                    content="¿Quieres recibir ayuda de la IA por privado? Para eso, debes ser miembro y además mecenas de The Math Guys. Si quieres unirte al servidor, únete en https://discord.gg/the-math-guys, y para unirte al club de sus donadores, puedes hacerlo en el siguiente enlace: https://patreon.com/MathLike\nRecuerda avisar a MathLike cuando hayas donado para que te den el rol.",
                )
                return
            if rol_mecenas not in guild_member.roles:
                await after.reply(
                    content="¿Quieres recibir ayuda de la IA por privado? Para eso, debes ser mecenas de The Math Guys. Si quieres unirte al club de los donadores, puedes hacerlo en el siguiente enlace: https://patreon.com/MathLike\nRecuerda avisar a MathLike cuando hayas donado para que te den el rol.",
                )
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
                    "role": "user",
                    "content": [],
                }
            )
            self.current_input[-1]["content"].append(
                {
                    "type": "input_text",
                    "text": io.getvalue(),
                }
            )
            self.current_input[-1]["content"].extend(await attachment_parts(after.attachments))
            self.message_count += 1
            if self.message_count > message_limit:
                self.previous_response_id = None
                self.message_count = 0
            if self.bot.user.mentioned_in(after) or isinstance(after.channel, discord.DMChannel):
                user_input = self.current_input.copy()
                there_was_function_call: bool = True
                self.current_input.clear()
                while there_was_function_call:
                    there_was_function_call = False
                    response = client.responses.create(
                        model="gpt-4.1",
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
                                        "type": {
                                            "type": "string",
                                            "description": "The type of output.",
                                            "enum": ["image", "video"],
                                        }
                                    },
                                    "required": ["title", "description", "is_3d", "type"],
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
                                time.sleep(2.0)  # Avoid rate limit
                                result = await render_manim(after, **arguments)
                            elif name == "bing_search":
                                time.sleep(2.0)  # Avoid rate limit
                                result = bing_search(**arguments)
                            elif name == "solve_math":
                                time.sleep(2.0)  # Avoid rate limit
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
                    time.sleep(2.0)  # Avoid rate limit

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return
        if isinstance(message.channel, discord.DMChannel):
            rol_mecenas = discord.utils.get(self.bot.guilds[0].roles, id=mecenas)
            guild_member = discord.utils.get(self.bot.guilds[0].members, id=message.author.id)
            if guild_member is None:
                await message.reply(
                    content="¿Quieres recibir ayuda de la IA por privado? Para eso, debes ser miembro y además mecenas de The Math Guys. Si quieres unirte al servidor, únete en https://discord.gg/the-math-guys, y para unirte al club de sus donadores, puedes hacerlo en el siguiente enlace: https://patreon.com/MathLike\nRecuerda avisar a MathLike cuando hayas donado para que te den el rol.",
                )
                return
            if rol_mecenas not in guild_member.roles:
                await message.reply(
                    content="¿Quieres recibir ayuda de la IA por privado? Para eso, debes ser mecenas de The Math Guys. Si quieres unirte al club de los donadores, puedes hacerlo en el siguiente enlace: https://patreon.com/MathLike\nRecuerda avisar a MathLike cuando hayas donado para que te den el rol.",
                )
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
                    "role": "user",
                    "content": [],
                }
            )
            self.current_input[-1]["content"].append(
                {
                    "type": "input_text",
                    "text": io.getvalue(),
                }
            )
            self.current_input[-1]["content"].extend(await attachment_parts(message.attachments))
            self.message_count += 1
            if self.message_count > message_limit:
                self.previous_response_id = None
                self.message_count = 0
            if self.bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
                user_input = self.current_input.copy()
                there_was_function_call: bool = True
                self.current_input.clear()
                while there_was_function_call:
                    there_was_function_call = False
                    response = client.responses.create(
                        model="gpt-4.1",
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
                                        "type": {
                                            "type": "string",
                                            "description": "The type of output.",
                                            "enum": ["image", "video"],
                                        }
                                    },
                                    "additionalProperties": False,
                                    "required": ["title", "description", "is_3d", "type"],
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
                                time.sleep(2.0)  # Avoid rate limit
                                result = await render_manim(message, **arguments)
                            elif name == "bing_search":
                                time.sleep(2.0)  # Avoid rate limit
                                result = bing_search(**arguments)
                            elif name == "solve_math":
                                time.sleep(2.0)  # Avoid rate limit
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
                    time.sleep(2.0)  # Avoid rate limit
