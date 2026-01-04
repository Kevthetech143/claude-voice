# Audio Module - Production Considerations

## Resampling Quality

**Current Implementation:** Linear interpolation (`normalize.py`)

**Status:** ⚠️ FUNCTIONAL BUT NOT OPTIMAL

**What it does:**
- Simple linear interpolation between samples
- Fast, zero dependencies
- Adequate for testing and MVP

**Limitations:**
- Not ideal for voice quality preservation
- May introduce artifacts at extreme sample rate changes (e.g., 8kHz → 48kHz)
- No anti-aliasing filter

**Production Recommendation:**

For production deployment, replace with a proper audio library:

### Option A: librosa (Recommended)
```python
import librosa
import numpy as np

def resample_with_librosa(audio: AudioData, target_rate: int) -> AudioData:
    # Load samples
    samples = np.frombuffer(audio.data, dtype=np.int16).astype(np.float32) / 32768.0

    # Resample with high-quality algorithm
    resampled = librosa.resample(
        samples,
        orig_sr=audio.sample_rate,
        target_sr=target_rate,
        res_type='kaiser_best'  # High quality
    )

    # Convert back to int16
    pcm_data = (resampled * 32768.0).astype(np.int16).tobytes()

    return AudioData(data=pcm_data, sample_rate=target_rate, ...)
```

**Pros:**
- Industry standard for audio ML
- Excellent quality (kaiser window)
- Well-tested

**Cons:**
- Heavy dependency (numpy, scipy, etc.)
- ~100MB install size

### Option B: pydub
```python
from pydub import AudioSegment

def resample_with_pydub(audio: AudioData, target_rate: int) -> AudioData:
    # Load from bytes
    audio_segment = AudioSegment.from_file(io.BytesIO(audio.data), format="wav")

    # Resample
    resampled = audio_segment.set_frame_rate(target_rate)
    resampled = resampled.set_channels(1)  # Mono

    # Export
    buffer = io.BytesIO()
    resampled.export(buffer, format="wav")

    return AudioData(data=buffer.getvalue(), ...)
```

**Pros:**
- Simple API
- Handles format conversions
- Uses ffmpeg (production-proven)

**Cons:**
- Requires ffmpeg installed
- Heavier than librosa for just resampling

### Decision for MVP:
**Keep current linear interpolation for now**
- Ships immediately
- Works for testing
- Document as "upgrade needed for production"

### When to upgrade:
- Before user-facing launch
- If voice quality issues reported
- If supporting extreme sample rate changes

## Silence Detection

**Current Implementation:** RMS threshold (0.01)

**Status:** ⚠️ UNTESTED ON REAL AUDIO

**Testing needed:**
- Record actual quiet speech (whisper)
- Record actual silence (no speech)
- Find threshold that separates them
- Test with background noise

**Production TODO:**
- Test on real samples
- Make threshold configurable
- Consider VAD (Voice Activity Detection) library like webrtcvad

## Metrics Storage

**Current Implementation:** In-memory counters

**Status:** ⚠️ LOST ON RESTART

**Production upgrade:**
```python
# Add Prometheus metrics
from prometheus_client import Counter, Histogram

stt_requests = Counter('stt_requests_total', 'Total STT requests')
stt_latency = Histogram('stt_latency_seconds', 'STT latency')
stt_errors = Counter('stt_errors_total', 'STT errors')
```

## Edge Cases Still TODO:
- [ ] Test with actual .mp3 files (not just WAV)
- [ ] Test with corrupted audio
- [ ] Test with very loud audio (clipping)
- [ ] Test with ultra-low sample rates (4kHz)
