"""
macOS say command TTS implementation
Uses built-in macOS speech synthesis (free, simple, no API required)
"""

import asyncio
import tempfile
import os
from typing import Optional
from pathlib import Path
from ..audio.types import AudioData, AudioFormat
from ..core.events import EventObserver, EventType


class MacOSSayTTS:
    """
    macOS `say` command implementation

    Advantages:
    - Free (no API costs)
    - Fast (local processing)
    - No network required
    - Simple integration

    Disadvantages:
    - macOS only
    - Lower quality than cloud services
    - Limited voice options
    """

    def __init__(self, voice: str = "Samantha", rate: int = 200):
        """
        Initialize macOS say TTS

        Args:
            voice: Voice name (e.g., "Samantha", "Alex", "Daniel")
                  Run `say -v ?` to see available voices
            rate: Speaking rate in words per minute (default 200)
        """
        self.voice = voice
        self.rate = rate

    async def speak(
        self,
        text: str,
        observer: Optional[EventObserver] = None
    ) -> None:
        """
        Convert text to speech and play it using macOS say

        Args:
            text: Text to speak
            observer: Optional event observer

        Raises:
            RuntimeError: If say command fails
            OSError: If macOS say is not available
        """
        # Emit start event
        if observer:
            observer.emit(
                EventType.TTS_START,
                {
                    "text": text,
                    "text_length": len(text),
                    "voice": self.voice,
                    "rate": self.rate
                }
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Run say command to play directly (no -o flag)
            # -v: voice, -r: rate
            cmd = [
                'say',
                '-v', self.voice,
                '-r', str(self.rate),
                text
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"say command failed: {error_msg}")

            # Calculate latency
            end_time = asyncio.get_event_loop().time()
            latency_ms = (end_time - start_time) * 1000

            # Calculate duration estimate
            word_count = len(text.split())
            estimated_duration_ms = (word_count / (self.rate / 60)) * 1000

            # Emit complete event
            if observer:
                observer.emit(
                    EventType.TTS_COMPLETE,
                    {
                        "latency_ms": latency_ms,
                        "estimated_duration_ms": estimated_duration_ms
                    }
                )

        except Exception as e:
            # Emit error event
            if observer:
                observer.emit(
                    EventType.TTS_ERROR,
                    {"error": str(e), "error_type": type(e).__name__}
                )
            raise

    @staticmethod
    async def get_available_voices() -> list[str]:
        """
        Get list of available voices on macOS

        Returns:
            List of voice names
        """
        process = await asyncio.create_subprocess_exec(
            'say', '-v', '?',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return []

        # Parse output (format: "VoiceName language # description")
        voices = []
        for line in stdout.decode().split('\n'):
            if line.strip():
                parts = line.split()
                if parts:
                    voices.append(parts[0])

        return voices
