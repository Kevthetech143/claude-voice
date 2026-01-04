"""
Main pipeline orchestrator
Coordinates STT → Claude → Chunker → TTS flow with observability
"""

import asyncio
from typing import AsyncIterator

from .events import EventObserver, EventType, InMemoryEventObserver


class VoicePipeline:
    """
    Main voice assistant pipeline
    Coordinates all components with full observability
    """

    def __init__(
        self,
        stt_provider,  # STTProvider protocol
        llm_provider,  # LLMProvider protocol
        tts_provider,  # TTSProvider protocol
        chunker,  # SentenceChunker
        observer: EventObserver | None = None,
    ):
        """
        Args:
            stt_provider: Speech-to-text implementation
            llm_provider: LLM implementation (Claude)
            tts_provider: Text-to-speech implementation
            chunker: Sentence chunker for streaming
            observer: Event observer for monitoring
        """
        self.stt = stt_provider
        self.llm = llm_provider
        self.tts = tts_provider
        self.chunker = chunker
        self.observer = observer or InMemoryEventObserver()

    async def process_audio(self, audio_data) -> str:
        """
        Process audio input through complete pipeline

        Args:
            audio_data: AudioData from microphone

        Returns:
            Transcript of user's speech

        Flow:
            1. Audio → STT
            2. Text → LLM (streaming)
            3. Tokens → Chunker → Sentences
            4. Sentences → TTS (parallel)
        """
        self.observer.emit(EventType.PIPELINE_START, {"audio_duration_ms": len(audio_data)})

        try:
            # Step 1: Transcribe audio
            transcript = await self.stt.transcribe(audio_data)

            if not transcript:
                self.observer.emit(EventType.PIPELINE_ERROR, {"error": "Empty transcript"})
                return ""

            # Step 2-4: Process through LLM → Chunker → TTS (streaming)
            await self._process_text_query(transcript)

            self.observer.emit(EventType.PIPELINE_COMPLETE, {"transcript": transcript})

            return transcript

        except Exception as e:
            self.observer.emit(
                EventType.PIPELINE_ERROR,
                {"error": str(e), "error_type": type(e).__name__},
            )
            raise

    async def process_text(self, text: str) -> None:
        """
        Process text query (for testing without audio)

        Args:
            text: User query text
        """
        self.observer.emit(EventType.PIPELINE_START, {"text": text[:100]})

        try:
            await self._process_text_query(text)
            self.observer.emit(EventType.PIPELINE_COMPLETE, {"text": text[:100]})

        except Exception as e:
            self.observer.emit(
                EventType.PIPELINE_ERROR,
                {"error": str(e), "error_type": type(e).__name__},
            )
            raise

    async def _process_text_query(self, text: str) -> None:
        """
        Core text processing: LLM → Chunker → TTS

        This is where the magic happens:
        - LLM streams tokens
        - Chunker buffers and emits sentences
        - TTS speaks sentences in parallel

        Args:
            text: User query text
        """
        # Get streaming LLM response
        token_stream = self.llm.query_stream(text)

        # Chunk into sentences
        sentence_stream = self.chunker.chunk_stream(token_stream)

        # Create TTS tasks for parallel processing
        tts_tasks = []

        async for sentence in sentence_stream:
            # Start TTS for this sentence immediately (don't wait)
            task = asyncio.create_task(self.tts.speak(sentence))
            tts_tasks.append(task)

        # Wait for all TTS to complete
        if tts_tasks:
            await asyncio.gather(*tts_tasks)

    def get_observer(self) -> EventObserver:
        """Get the event observer for inspection"""
        return self.observer
