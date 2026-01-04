#!/bin/bash
# Voice Assistant Launcher
# Activates Python 3.12 venv and runs voice mode

cd "$(dirname "$0")"
source venv_py312/bin/activate
python3 run_voice.py
