#!/usr/bin/env python3
"""
Setup script for local voice models
Downloads and caches Whisper and Piper models
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.models import ModelManager


def main():
    """Setup local voice models"""
    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Local Model Setup")
    print("=" * 70)

    manager = ModelManager()

    print("\n📊 Available Models:")
    print("\nWhisper STT:")
    for name, info in ModelManager.WHISPER_MODELS.items():
        print(f"  • {name:8} - {info.description}")

    print("\nTTS Options:")
    print("  • macOS say (built-in)   - Fast, robotic voice, zero setup")
    print("  • Piper TTS              - Natural voice, requires manual install")
    print("  • ElevenLabs API         - Premium quality, requires API key")

    print("\n" + "=" * 70)
    print("Recommended Setup: Whisper 'small' + macOS say")
    print("(Piper TTS has dependency issues - use macOS say for now)")
    print("=" * 70)

    # Check what's already cached
    cached = manager.list_cached_models()
    if cached['whisper'] or cached['piper']:
        print("\n✅ Already cached:")
        if cached['whisper']:
            print(f"   Whisper: {', '.join(cached['whisper'])}")
        if cached['piper']:
            print(f"   Piper: {', '.join(cached['piper'])}")

    # Prompt for download
    print("\n🎯 Which Whisper model to download?")
    print("   1. Recommended: small (~466MB, balanced)")
    print("   2. Fast: tiny (~75MB, fastest)")
    print("   3. High Quality: medium (~1.5GB, best quality)")
    print("   4. All models (for testing)")
    print("   5. Skip (use already cached models)")
    print("\n   Note: TTS uses macOS say (built-in, zero download)")

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        print("\n📥 Downloading Whisper small...")
        manager.get_whisper_model_path("small")
        print("   TTS: macOS say (already installed)")

    elif choice == "2":
        print("\n📥 Downloading Whisper tiny...")
        manager.get_whisper_model_path("tiny")
        print("   TTS: macOS say (already installed)")

    elif choice == "3":
        print("\n📥 Downloading Whisper medium...")
        manager.get_whisper_model_path("medium")
        print("   TTS: macOS say (already installed)")

    elif choice == "4":
        print("\n📥 Downloading all Whisper models...")
        for model in ["tiny", "base", "small", "medium"]:
            manager.get_whisper_model_path(model)
        print("   TTS: macOS say (already installed)")

    elif choice == "5":
        print("\n⏭️  Skipping download")

    else:
        print("\n❌ Invalid choice")
        return

    # Summary
    print("\n" + "=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)

    cached = manager.list_cached_models()
    cache_size = manager.get_cache_size_mb()

    print(f"\n📦 Cached Models ({cache_size:.1f}MB total):")
    if cached['whisper']:
        print(f"   Whisper: {', '.join(cached['whisper'])}")
    if cached['piper']:
        print(f"   Piper: {', '.join(cached['piper'])}")

    print(f"\n📁 Cache location: {manager.cache_dir}")

    print("\n🚀 Next Steps:")
    print("   1. Run: python demo_local_voice.py")
    print("   2. Or configure in your code:")
    print("      from src.core.providers import ProviderConfig")
    print("      config = ProviderConfig.local_only()")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
