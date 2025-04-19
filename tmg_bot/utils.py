import discord
import emoji
import pathlib
import subprocess
import base64
import os
import cv2
from .client import client
import tempfile
import math
from io import BytesIO
from PIL import Image

from .regex import tex_message
from .tex_templates import DEFAULT_TEX_TEMPLATE
from .client import client
from .regex import mentions, double_quotes, single_quotes


def has_audio(filename: str) -> bool:
    """Check if the file has audio."""
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=nb_streams", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return bool(int(result.stdout) - 1)


def mp4_to_mp3(mp4_path: str, mp3_path: str) -> None:
    """Convert MP4 file to MP3."""
    command = f"ffmpeg -i {mp4_path} -vn -ar 44100 -ac 2 -b:a 192k {mp3_path}"
    subprocess.run(command, shell=True, check=True)


def process_video(video_data: bytes) -> list:
    """Process video data and return parts for Gemini API."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(video_data)
        temp_video.seek(0)
        has_a = has_audio(temp_video.name)
        video_stream = cv2.VideoCapture(temp_video.name)
        frames_and_transcription = []
        frames_and_transcription.append(
            {
                "type": "input_text",
                "text": "A video is starting right now. The next inputs are 40 (or less) evenly spaced frames and the last one is the transcription, if any audio. There's no transcription if it's null, empty or senseless.",
            }
        )
        frame_step = math.ceil(video_stream.get(cv2.CAP_PROP_FRAME_COUNT) / 10)
        frame_count = 0
        while video_stream.isOpened():
            success, frame = video_stream.read()
            if not success:
                break
            bio = BytesIO()
            Image.fromarray(frame).convert("RGB").save(bio, format="JPEG")
            bio.seek(0)
            data = bio.read()
            data = base64.b64encode(data).decode("utf-8")
            if frame_count % frame_step == 0:
                print(data)
                frames_and_transcription.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{data}",
                        "detail": "low",
                    }
                )
            frame_count += 1
        video_stream.release()
        if has_a:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                mp4_to_mp3(temp_video.name, temp_audio.name)
                temp_audio.seek(0)
                transcription = client.audio.transcriptions.create(
                    file=temp_audio.name,
                    model="whisper"
                )
                text = transcription.text
                print(text)
                frames_and_transcription.append(
                    {
                        "type": "input_text",
                        "text": f"# Transcription\n{text}",
                    }
                )
    frames_and_transcription.append(
        {
            "type": "input_text",
            "text": "The video has ended.",
        }
    )
    return frames_and_transcription


async def attachment_parts(attachments: list[discord.Attachment]) -> list:
    """Convert attachments to parts for the OpenAI API."""
    parts = []
    for attachment in attachments:
        if attachment.content_type.startswith("image/"):
            image_data = await attachment.read()
            encoded_image = base64.b64encode(image_data).decode("utf-8")
            parts.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{attachment.content_type};base64,{encoded_image}",
                    "detail": "high",
                }
            )
        elif attachment.content_type.startswith("video/"):
            video_data = await attachment.read()
            parts.extend(process_video(video_data))
        elif attachment.content_type.startswith("audio/"):
            audio_data = await attachment.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                temp_audio.write(audio_data)
                temp_audio.seek(0)
                transcription = client.audio.transcriptions.create(
                    file=temp_audio.name,
                    model="whisper"
                )
                text = transcription.text
                print("Transcription:", text)
                parts.append(
                    {
                        "type": "input_text",
                        "text": f"An audio has been sent.\n\n# Transcription\n{text}",
                    }
                )
                os.remove(temp_audio.name)
        elif attachment.content_type.startswith("application/pdf"):
            pdf_data = await attachment.read()
            file = client.files.create(
                file=pdf_data,
                purpose="user_data"
            )
            parts.append(
                {
                    "type": "input_file",
                    "file_id": file.id,
                }
            )
    return parts


def change_prefix_and_suffix(tex: str) -> str:
    """Change the prefix and suffix of a TeX string."""
    if tex.startswith("\\(") and tex.endswith("\\)"):
        return f"${tex[2:-2]}$"
    elif tex.startswith("\\[") and tex.endswith("\\]"):
        return f"$$\\{tex[2:-2]}$$"
    else:
        return tex


def fix_tex_bugs(text: str) -> str:
    without_emojis = emoji.replace_emoji(text, "")
    without_mentions = mentions.sub("Usuario de Discord", without_emojis)
    beautify_quotes = double_quotes.sub(r"“\1”", without_mentions)
    beautify_quotes = single_quotes.sub(r"‘\1’", beautify_quotes)
    force_dollars = tex_message.sub(
        lambda m: change_prefix_and_suffix(m.group(0)), beautify_quotes
    )
    return force_dollars


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
