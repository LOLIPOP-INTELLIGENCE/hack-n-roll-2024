import RPi.GPIO as GPIO
import time
import json
import numpy as np
import threading
import sys
from datetime import datetime
import base64
import requests
import queue
import pygame
import subprocess
import sounddevice as sd
import pyaudio
import wave
pygame.mixer.init()

import os
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable")


img_path = "test.png"
command = ["sudo", "libcamera-still", "-o", "test.png"]

GPIO.setmode(GPIO.BCM)  # BCM pin-numbering scheme
button_pin = 4# replace with your GPIO pin
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Set pin as an input pin
def button_pressed():
    # Check if the button is pressed
    button_state = GPIO.input(button_pin)
    return not button_state  # Return True if pressed, False otherwise
# Audio recording parameters
FORMAT = pyaudio.paInt16  # Audio format
CHANNELS = 1              # Number of channels
RATE = 48000              # Bit Rate
CHUNK = 1024              # Number of frames per buffer
RECORD_SECONDS = 10       # Record time

def record_audio(filename):
    WAVE_OUTPUT_FILENAME = filename  # Output filename
    audio = pyaudio.PyAudio()
    # for i in range(audio.get_device_count()):
    #     print(audio.get_device_info_by_index(i))
    # Start recording
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK,input_device_index=2)
    print("Recording...")
    frames = []

    # Loop until the button is released
    while GPIO.input(button_pin) == True:
        data = stream.read(CHUNK)
        frames.append(data)

    print("Finished recording")

    # Stop recording
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save the recorded data as a WAV file
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# def record_audio(filename):
#     WAVE_OUTPUT_FILENAME = filename  # Output filename
# # Initialize PyAudio
#     audio = pyaudio.PyAudio()

#     # Start recording
#     stream = audio.open(format=FORMAT, channels=CHANNELS,
#                         rate=RATE, input=True,
#                         frames_per_buffer=CHUNK)
#     print("recording...")
#     frames = []

#     for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
#         data = stream.read(CHUNK)
#         frames.append(data)

#     print("finished recording")

#     # Stop recording
#     stream.stop_stream()
#     stream.close()
#     audio.terminate()

#     # Save the recorded data as a WAV file
#     wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
#     wf.setnchannels(CHANNELS)
#     wf.setsampwidth(audio.get_sample_size(FORMAT))
#     wf.setframerate(RATE)
#     wf.writeframes(b''.join(frames))
#     wf.close()

# Run the command
result = subprocess.run(command, capture_output=True, text=True)
start_time = datetime.now()

def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

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

def tts_worker(response_queue, audio_queue, end_of_responses, condition):
    counter = 0
    while True:
        response = response_queue.get()
        if response is None:
            response_queue.task_done()
            with condition:
                end_of_responses.set()
                condition.notify_all()
            break
        audio_file = f"speech/tts_output_{counter}.mp3"
        tts(response, audio_file)
        with condition:
            audio_queue.put(audio_file)
            condition.notify()
        response_queue.task_done()
        counter += 1

def play_worker(audio_queue, end_of_responses, condition):
    while True:
        with condition:
            while audio_queue.empty() and not end_of_responses.is_set():
                condition.wait()
            if end_of_responses.is_set() and audio_queue.empty():
                break
            audio_file = audio_queue.get()
        play_audio(audio_file)
        audio_queue.task_done()


def stream_response(responses):
    response_queue = queue.Queue()
    audio_queue = queue.Queue()
    end_of_responses = threading.Event()
    condition = threading.Condition()

    tts_thread = threading.Thread(target=tts_worker, args=(response_queue, audio_queue, end_of_responses, condition))
    play_thread = threading.Thread(target=play_worker, args=(audio_queue, end_of_responses, condition))
    tts_thread.start()
    play_thread.start()

    # Enqueue the responses
    all_responses = responses.split(".")
    all_responses = [response for response in all_responses if response.strip()]
    for response in all_responses:
        response_queue.put(response)

    # Signal the tts_worker to exit
    response_queue.put(None)

    # Wait for the queues to be processed
    response_queue.join()
    audio_queue.join()

    # Wait for the worker threads to finish
    tts_thread.join()
    play_thread.join()

def tts(response, audio_file):
    print(f"calling tts on: {response}")
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

    with open(audio_file, 'wb') as file:
        file.write(response.content)


def play_audio(file):
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()
    # Keep the script running until the sound is finished
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

# Check if the command was successful
# if result.returncode == 0:
#     start_time = datetime.now()
#     record_audio("speech/test.wav")
#     print("Record Audio: ", datetime.now() - start_time)

#     original_start_time = datetime.now()

#     start_time = datetime.now()
#     question = stt("speech/test.wav")
#     print("Question: ", question)
#     print("Picture clicked!")
#     question = f"Describe this image to a visually impaired person. Here's what the blind person has asked/said about the image: '{question}'. Please provide a detailed and accessible description, focusing on important elements and context."
#     gemini_response = gpt(img_path, question)
#     print("GPT: ", datetime.now() - start_time)
#     print(gemini_response)
#     tts("Let me take a look at that.","speech/speech.mp3")
#     play_audio("speech/speech.mp3")
#     tart_time = datetime.now()
#     stream_response(gemini_response)
#     final_time = datetime.now()
#     print("TTS: ", datetime.now() - start_time)
#     start_time = datetime.now()
#     play_audio("speech/speech.mp3")
#     print("Play Audio: ", datetime.now() - start_time)
#     print("Total Time: ", final_time - original_start_time)

# else:
#     print("Error:")
#     print(result.stderr)

try:
    while True:
        # Read the state of the pushbutton
        button_state = GPIO.input(button_pin)
        if button_state == True:  # Button is pressed
            print("Button Pressed!")
            start_time = datetime.now()
            record_audio("speech/test.wav")
            print("Record Audio: ", datetime.now() - start_time)

            original_start_time = datetime.now()

            start_time = datetime.now()
            question = stt("speech/test.wav")
            print("Question: ", question)
            print("Picture clicked!")
            question = f"Describe this image to a visually impaired person. Here's what the blind person has asked/said about the image: '{question}'. Please provide a detailed and accessible description, focusing on important elements and context."
            gemini_response = gpt(img_path, question)
            print("GPT: ", datetime.now() - start_time)
            print(gemini_response)
            tts("Let me take a look at that.","speech/speech.mp3")
            play_audio("speech/speech.mp3")
            tart_time = datetime.now()
            stream_response(gemini_response)
            final_time = datetime.now()
            print("TTS: ", datetime.now() - start_time)
            start_time = datetime.now()
            play_audio("speech/speech.mp3")
            print("Play Audio: ", datetime.now() - start_time)
            print("Total Time: ", final_time - original_start_time)            
        else:
            print("Button not pressed!")
        time.sleep(0.2)  # Add a debounce delay

except KeyboardInterrupt:
    GPIO.cleanup()  # Clean up GPIO on CTRL+C exit

GPIO.cleanup()  # Clean up GPIO on normal exit