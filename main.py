from openai import OpenAI
import json
import openai
from google.cloud import texttospeech
from google.cloud import speech
from playsound import playsound
import google.generativeai as genai
from pathlib import Path


import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import sys
import os
import time
from datetime import datetime
from pydub import AudioSegment
import io
import tempfile
import PIL.Image


import re
client = OpenAI(api_key="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")
genai.configure(api_key="AIzaSyA9rnUXpz3roR-Pk7PCZezo8j558I7dJv8")
img_path = "label.png"


def record_audio(filename):
    def callback(indata, frames, time, status):
        nonlocal data, stop_recording
        if status:
            print(status, file=sys.stderr)
        if stop_recording.is_set():
            raise sd.CallbackStop
        data.append(indata.copy())

    # Define the sample rate and query the device's max input channels
    sample_rate = 44100
    num_input_channels = sd.query_devices(None, 'input')['max_input_channels']

    try:
        data = []
        stop_recording = threading.Event()

        with sd.InputStream(samplerate=sample_rate, channels=num_input_channels, callback=callback):
            print("Recording started...")
            input("Press Enter to stop the recording...")
            stop_recording.set()

        # Concatenate all recorded audio data into one NumPy array
        audio_data = np.concatenate(data, axis=0)

        # Save the audio data to the specified file as WAV (because MP3 is not supported by soundfile)
        import soundfile as sf
        sf.write(filename, audio_data, sample_rate)

        print(f"Recording saved to {filename}")

    except Exception as ex:
        print(ex)


def stt(file):
    transcript = client.audio.transcriptions.create(
        model="whisper-1", file=open(file, "rb"))
    return transcript.text


def gemini(img_path, question):
    model = genai.GenerativeModel('gemini-pro-vision')
    response = model.generate_content([question, PIL.Image.open(img_path)])
    return response.text


def tts(response):
    speech_file_path = Path(__file__).parent / "speech.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=response
    )

    response.stream_to_file(speech_file_path)


def play_audio(file):
    playsound(file)


start_time = datetime.now()
record_audio("test.wav")
print("Record Audio: ", datetime.now() - start_time)

original_start_time = datetime.now()

start_time = datetime.now()
question = stt("test.wav")
print("STT: ", datetime.now() - start_time)
print(question)
start_time = datetime.now()
tts("Let me take a look at that.")
play_audio("speech.mp3")

gemini_response = gemini(img_path, question)
print("Gemini: ", datetime.now() - start_time)
print(gemini_response)
start_time = datetime.now()

tts(gemini_response)
print("TTS: ", datetime.now() - start_time)
start_time = datetime.now()
play_audio("speech.mp3")
print("Play Audio: ", datetime.now() - start_time)

print("Total Time: ", datetime.now() - original_start_time)