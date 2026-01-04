# Claude Voice Assistant - Production Architecture

**Built by ALPHA + BETA agents | Production-ready | AI-testable end-to-end**

## Design Principles

1. **AI-First Testing** - Every component mockable and verifiable by AI
2. **Observable Pipeline** - All stages emit events for monitoring
3. **Dependency Injection** - Mock any component for isolated testing
4. **Dual-Mode Operation** - Test mode (text I/O) + Production mode (voice I/O)
5. **Production Grade** - SRE patterns from Google/Anthropic

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLAUDE VOICE ASSISTANT                │
└─────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │ Voice Input  │
                    │ (mockable)   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Wake Word   │
                    │  (optional)  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │     STT      │
                    │  Whisper API │
                    │   ~500ms     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Event Queue  │◄────── Observable
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    Claude    │
                    │ Code via MCP │
                    │  (streaming) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Sentence   │
                    │    Chunker   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │     TTS      │
                    │ ElevenLabs/  │
                    │  macOS say   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Audio Output │
                    │ (verifiable) │
                    └──────────────┘
```

## Component Specifications

### 1. Audio Input Module (BETA owns)
- **Interface:** `AudioSource` protocol
- **Implementations:**
  - `MicrophoneSource` (production)
  - `MockAudioSource` (testing - plays pre-recorded audio)
  - `SilentSource` (testing - simulates silence)
- **Testability:** AI can inject test audio files
- **Metrics:** Volume level, sample rate, buffer health

### 2. STT Module (BETA owns)
- **Service:** OpenAI Whisper API
- **Cost:** $0.006/minute
- **Latency Target:** 500ms
- **Interface:** `SpeechRecognizer` protocol
  - `transcribe(audio: AudioData) -> Future[String]`
- **Testing:** Mock recognizer returns predefined transcripts
- **Metrics:** API latency, accuracy (if reference available)

### 3. Claude Integration (ALPHA owns)
- **Method:** MCP server (uses existing Claude Code subscription)
- **Streaming:** Token-by-token via MCP
- **Interface:** `ClaudeClient` protocol
  - `query(text: String) -> AsyncIterator[String]`
- **Testing:** Mock client returns scripted responses
- **Metrics:** Time to first token, total latency, token count

### 4. Sentence Chunker (ALPHA owns)
- **Function:** Buffer tokens, emit on sentence boundaries
- **Logic:** Detect `.`, `!`, `?` with context awareness
- **Testing:** Unit tests with various sentence patterns
- **Metrics:** Chunks emitted, average chunk size

### 5. TTS Module (BETA owns)
- **Primary:** ElevenLabs streaming API
- **Fallback:** macOS `say` command
- **Interface:** `TextToSpeech` protocol
  - `speak(text: String) -> Future[AudioData]`
- **Testing:** Mock TTS logs text instead of speaking
- **Metrics:** API latency, audio duration

### 6. Event Queue (ALPHA owns)
- **Purpose:** Observable pipeline for testing
- **Events:**
  - `AudioCaptured(duration, level)`
  - `TranscriptionStarted()`
  - `TranscriptionComplete(text, latency)`
  - `ClaudeQueryStarted(text)`
  - `ClaudeTokenReceived(token)`
  - `ClaudeComplete(total_tokens, latency)`
  - `SentenceReady(text)`
  - `TTSStarted(text)`
  - `TTSComplete(duration)`
  - `PipelineComplete(total_latency)`
- **Testability:** AI reads event log to verify behavior

## Test Harness Design

### Test Levels

**Level 1: Unit Tests** (per component)
- Mock all dependencies
- Test edge cases (empty input, errors, timeouts)
- Fast (<100ms per test)

**Level 2: Integration Tests** (pairs of components)
- STT + Claude
- Claude + TTS
- Full pipeline with mocks

**Level 3: End-to-End Tests** (full system)
- Pre-recorded audio → final TTS output
- AI verifies event log matches expected flow
- Latency benchmarks

### AI Test Interface

```python
# AI can run tests like this:
result = await test_harness.run_scenario(
    audio_input="test_audio/hello_claude.wav",
    expected_transcript="Hello Claude",
    expected_response_contains="Hello",
    max_latency_ms=2000
)

# AI verifies:
assert result.success
assert result.total_latency < 2000
assert "Hello" in result.tts_text
```

## Production Readiness Checklist

### Reliability
- [ ] Health checks for all external APIs
- [ ] Graceful degradation (STT fails → retry, TTS fails → fallback)
- [ ] Circuit breakers for API calls
- [ ] Timeout handling at every stage

### Observability
- [ ] Structured logging (JSON format)
- [ ] Event stream for monitoring
- [ ] Latency metrics per stage
- [ ] Error rate tracking

### Performance
- [ ] Target: <1s wake word to first speech
- [ ] STT: 500ms
- [ ] Claude first token: 300ms
- [ ] TTS first audio: 200ms
- [ ] Parallel processing (sentence chunking)

### Security
- [ ] API keys from environment (never hardcoded)
- [ ] User consent for microphone access
- [ ] Audio not logged/stored (privacy)
- [ ] MCP security model followed

### Cost Control
- [ ] STT: $0.006/min
- [ ] Claude: ~$0.03-0.15/query (via existing subscription)
- [ ] TTS: $0.10/min (ElevenLabs) or $0 (macOS say)
- [ ] Total target: <$0.20/min

## Technology Stack

**Language:** Python 3.11+
**Core:**
- `anthropic-mcp` - Claude Code integration
- `openai` - Whisper API
- `elevenlabs` - TTS (optional, premium)
- `pyaudio` - Audio I/O
- `asyncio` - Async/await pipeline

**Testing:**
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities

**Production:**
- `structlog` - Structured logging
- `prometheus-client` - Metrics (optional)

## File Structure

```
claude-voice/
├── ARCHITECTURE.md          # This file
├── README.md               # User guide
├── requirements.txt        # Dependencies
├── pyproject.toml         # Project config
│
├── src/
│   ├── core/
│   │   ├── pipeline.py        # Main orchestrator (ALPHA)
│   │   ├── events.py          # Event queue (ALPHA)
│   │   └── config.py          # Configuration
│   │
│   ├── audio/
│   │   ├── input.py           # Audio capture (BETA)
│   │   └── output.py          # Audio playback (BETA)
│   │
│   ├── stt/
│   │   ├── whisper.py         # Whisper integration (BETA)
│   │   └── mock.py            # Mock STT for testing
│   │
│   ├── llm/
│   │   ├── claude_mcp.py      # MCP client (ALPHA)
│   │   ├── chunker.py         # Sentence chunker (ALPHA)
│   │   └── mock.py            # Mock Claude for testing
│   │
│   └── tts/
│       ├── elevenlabs.py      # ElevenLabs integration (BETA)
│       ├── macos_say.py       # macOS say fallback (BETA)
│       └── mock.py            # Mock TTS for testing
│
├── tests/
│   ├── unit/              # Unit tests (both agents)
│   ├── integration/       # Integration tests (both agents)
│   ├── e2e/              # End-to-end tests (both agents)
│   └── fixtures/         # Test audio files, expected outputs
│
├── test_harness/
│   ├── runner.py         # AI test interface (ALPHA)
│   ├── scenarios.py      # Test scenarios (ALPHA)
│   └── validators.py     # Result validators (ALPHA)
│
└── app/
    ├── main.py           # CLI entry point
    └── ui.py             # Optional GUI (Phase 2)
```

## Development Phases

### Phase 1: Core Pipeline (Week 1)
- ALPHA: Event queue, Claude MCP integration, sentence chunker
- BETA: STT (Whisper), TTS (macOS say first, then ElevenLabs)
- Deliverable: Text-in → Claude → TTS working

### Phase 2: Test Harness (Week 1)
- ALPHA: Test runner, scenario framework, validators
- BETA: Audio test fixtures, mock implementations
- Deliverable: AI can run full E2E tests

### Phase 3: Audio Integration (Week 2)
- BETA: Microphone input, wake word (Porcupine)
- ALPHA: Pipeline integration, error handling
- Deliverable: Voice-in → voice-out working

### Phase 4: Production Hardening (Week 2)
- Both: Health checks, circuit breakers, monitoring
- Both: Performance optimization
- Both: Documentation
- Deliverable: Production-ready system

## Success Criteria

1. **AI can test it:** Full E2E test suite runnable by AI
2. **Fast:** <1s latency from wake word to first speech
3. **Reliable:** 99%+ success rate on valid audio
4. **Observable:** Event log shows exactly what happened
5. **Production-grade:** Follows Google SRE patterns
6. **Cost-effective:** <$0.20/min operating cost

## References

- Anthropic Engineering Blog: Building Effective Agents
- Google SRE: Production Readiness Reviews
- AssemblyAI: Voice AI Stack 2025
- OpenAI Whisper API docs
- ElevenLabs Streaming API docs
