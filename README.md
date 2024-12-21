# YouTube Audio Downloader & AI Transcriber

This script downloads audio from a specified YouTube channel,
uses AI (via the Groq API) to transcribe the audio, and then
saves the formatted text.

## Requirements
1. Python 3  
2. Dependencies:
   - requests  
   - google-api-python-client  
   - yt-dlp  
   - groq  

Example installation on Linux:
pip install requests google-api-python-client yt-dlp groq

## Environment Variables
- GROQ_API_KEY: Groq API key (required for AI transcription)  
- YT_API_KEY: YouTube API key  
- CHANNEL_ID: Target YouTube channel ID  

## Usage
1. Set the environment variables.  
2. Run:
   python main.py

Audio files go in "audio_files" and transcriptions appear in
"transcriptions".
