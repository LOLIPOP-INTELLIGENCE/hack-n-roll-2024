import json
from playsound import playsound
import sounddevice as sd
import numpy as np
import threading
import sys
from datetime import datetime
import base64
import requests


import re

api_key = "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"


def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

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
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        'Authorization': f'Bearer {api_key}',  # Replace 'TOKEN' with your actual token
    }
    files = {
        'file': open(file, 'rb'),  # Replace with your file path
    }

    data = {
        'model' : 'whisper-1'
    }

    response = requests.post(url, headers=headers, files=files, data=data)
    return (response.json()['text'])    



def gpt(img_path, question):
    base64_image = encode_image(img_path)

    headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
    }

    payload = {
    "model": "gpt-4-vision-preview",
    "messages": [
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": f"{question}"
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
            }
        ]
        }
    ],
    "max_tokens": 1024,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    return response.json()['choices'][0]['message']['content']

def stream_response(responses):
    responses = responses.split(".")
    for response in responses:
        tts(response)

        play_audio("speech/speech.mp3")
def tts(response):
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "tts-1",
        "input": f"{response}",
        "voice": "alloy"
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    with open('speech/speech.mp3', 'wb') as file:
        file.write(response.content)


def play_audio(file):
    playsound(file)


start_time = datetime.now()
record_audio("speech/test.wav")
print("Record Audio: ", datetime.now() - start_time)

original_start_time = datetime.now()

start_time = datetime.now()
question = stt("speech/test.wav")
print("STT: ", datetime.now() - start_time)
print(question)
start_time = datetime.now()
tts("Let me take a look at that.")
play_audio("speech/speech.mp3")

gemini_response = gpt(img_path, question)
print("GPT: ", datetime.now() - start_time)
print(gemini_response)

start_time = datetime.now()

stream_response(gemini_response)

final_time = datetime.now()

print("TTS: ", datetime.now() - start_time)
start_time = datetime.now()
play_audio("speech/speech.mp3")
print("Play Audio: ", datetime.now() - start_time)

print("Total Time: ", final_time - original_start_time)