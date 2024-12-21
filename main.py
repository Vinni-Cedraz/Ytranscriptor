#!/usr/bin/env python3

import os
import sys
import requests
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from groq import Groq

# Set up your API keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YT_API_KEY")

if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY is not set.")
    sys.exit(1)

if not YOUTUBE_API_KEY:
    print("Error: YOUTUBE_API_KEY is not set.")
    sys.exit(1)

# YouTube channel ID
channel_id = os.environ.get("CHANNEL_ID")  # Replace with your channel ID

# Create directories to save audio files and transcriptions
os.makedirs("audio_files", exist_ok=True)
os.makedirs("transcriptions", exist_ok=True)


def get_video_ids(youtube, channel_id):
    """Retrieve video IDs from a YouTube channel."""
    video_ids = []
    request = youtube.search().list(
        part="id", channelId=channel_id, maxResults=50, order="date", type="video"
    )

    while request:
        response = request.execute()
        for item in response.get("items", []):
            video_ids.append(item["id"]["videoId"])
        request = youtube.search().list_next(request, response)

    return video_ids


def get_video_details(youtube, video_id):
    """Retrieve video details."""
    request = youtube.videos().list(part="snippet,contentDetails", id=video_id)
    response = request.execute()
    items = response.get("items", [])
    return items[0] if items else None


def check_for_transcription(youtube, video_id):
    """Check if the video has a transcription."""
    request = youtube.captions().list(part="snippet", videoId=video_id)
    response = request.execute()
    for item in response.get("items", []):
        if item["snippet"]["trackKind"] == "ASR":
            continue  # Ignore automatically generated captions
        return True
    return False


def download_audio(video_id, index):
    """Download audio from a YouTube video using yt-dlp."""
    from yt_dlp import YoutubeDL

    # Base file name without extension
    audio_file_basename = os.path.join("audio_files", f"{index}")

    # Final audio file path with .mp3 extension
    audio_file_path = f"{audio_file_basename}.mp3"

    # Skip if audio file already exists
    if os.path.exists(audio_file_path):
        print(f"Audio file {audio_file_path} already exists. Skipping download.")
        return audio_file_path

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_file_basename,  # No extension here
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",  # Use 128 kbps for sufficient quality
                "nopostoverwrites": False,
            }
        ],
        "quiet": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return audio_file_path  # Return the correct path with .mp3 extension
    except Exception as e:
        print(f"Error downloading audio for video ID {video_id}: {e}")
        return None


def transcribe_audio(audio_file_path):
    """Transcribe audio file using Groq API."""
    audio_file_types = {".mp3", ".wav", ".m4a", ".flac"}
    if not Path(audio_file_path).suffix.lower() in audio_file_types:
        raise ValueError(
            f"Unsupported audio format for {audio_file_path}. Supported formats: {audio_file_types}"
        )

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    with open(audio_file_path, "rb") as f:
        files = {"file": f}
        data = {"model": "whisper-large-v3"}
        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 200:
        return response.json()["text"]
    else:
        raise Exception(f"Transcription failed: {response.text}")


def query_groq(prompt):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.2-90b-vision-preview",
    )
    return chat_completion.choices[0].message.content


def format_transcription(transcription):
    """Format the transcription using LLM."""
    prompt = f"""Edit the following transcription into topics using markdown. Try
    to recognize when something is a song lyric instead of conversational
    text.:\n\n{transcription}"""
    formatted_transcription = query_groq(prompt)
    return formatted_transcription


def process_video(youtube, video_id, index):
    """Process a single video: download audio, transcribe, and format."""
    video_details = get_video_details(youtube, video_id)
    if not video_details:
        print(f"Video details not found for ID: {video_id}")
        return

    title = video_details["snippet"]["title"]
    file_name = f"{index}.md"
    file_path = os.path.join("transcriptions", file_name)

    print(f"Processing video: {title}")

    # Check if the transcription file already exists
    if os.path.exists(file_path):
        print(
            f"Transcription file {file_path} already exists. Skipping transcription and formatting."
        )
        return

    # Check if the video has a transcription
    if check_for_transcription(youtube, video_id):
        print(
            f"Video ID {video_id} already has a transcription. Skipping download and transcription."
        )
        return

    audio_file_path = download_audio(video_id, index)
    if not audio_file_path:
        print(f"Failed to download audio for video ID: {video_id}")
        return

    try:
        transcription = transcribe_audio(audio_file_path)
    except Exception as e:
        print(f"Transcription failed for {audio_file_path}: {e}")
        return

    formatted_transcription = format_transcription(transcription)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(formatted_transcription)
        print(f"Saved edited transcription to {file_path}")
    except Exception as e:
        print(f"Failed to write transcription to {file_path}: {e}")


def main():
    # Initialize YouTube Data API client
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # Fetch all video IDs from the channel
    try:
        video_ids = get_video_ids(youtube, channel_id)
        print(f"Found {len(video_ids)} videos.")
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        sys.exit(1)

    # Process each video
    for index, video_id in enumerate(video_ids, start=1):
        process_video(youtube, video_id, index)


if __name__ == "__main__":
    main()
