import json
from playsound import playsound
import sounddevice as sd
import numpy as np
import threading
import sys
from datetime import datetime
import base64
import requests
import queue
import os

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable")


img_path = "images/image.jpg"


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
tts("Let me take a look at that.","speech/speech.mp3")
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