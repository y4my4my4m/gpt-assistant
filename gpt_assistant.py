import speech_recognition as sr
import openai
import requests
import json
import sys
import os
import subprocess
from dotenv import load_dotenv
from gtts import gTTS
import tempfile


# Load environment variables from .env file
load_dotenv()

# Set your API keys from the environment variables
openai_api_key = os.getenv('OPENAI_KEY')
openai_system_prompt = os.getenv('OPENAI_SYSTEM')
use_whisper = os.getenv('USE_WHISPER')
use_elevenlabs = os.getenv('USE_ELEVENLABS')
elevenlabs_api_key = os.getenv('ELEVENLABS_KEY')
elevenlabs_voice = os.getenv('ELEVENLABS_VOICE')
elevenlabs_latency = os.getenv('ELEVENLABS_LATENCY')

use_whisper_bool = use_whisper.lower() == 'true'
use_elevenlabs_bool = use_elevenlabs.lower() == 'true'

# Initialize the speech recognizer
recognizer = sr.Recognizer()

conversation_history = []

def listen_for_speech():
    with sr.Microphone() as source:  
        # Suppress ALSA output
        sys.stdout = open(os.devnull, 'w')
        recognizer.adjust_for_ambient_noise(source)
        sys.stdout = sys.__stdout__

        print("Listening...")
        audio = recognizer.listen(source)
    return audio

def transcribe_with_whisper(file_path):
    with open(file_path, "rb") as file:
        transcription = openai.Audio.transcribe("whisper-1", file)
        print("[WHISPER] You said: " + transcription['text'])
    return transcription['text']

def transcribe_speech(audio):
    if use_whisper_bool:
        return transcribe_with_whisper(audio)
    else:
        try:
            text = recognizer.recognize_google(audio)
            print("[gTTS] You said: " + text)
            return text
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))

def query_chatgpt(prompt):
    openai.api_key = openai_api_key
    conversation_history.append({"role": "user", "content": prompt})
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history
        )
        chat_response = response.choices[0].message['content'].strip()
        print("GPT-3.5 response: ", chat_response)
        conversation_history.append({"role": "assistant", "content": chat_response})
        return chat_response
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def text_to_speech(text):
    if use_elevenlabs_bool:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice}/stream"
        query_params = {
            "optimize_streaming_latency": elevenlabs_latency
        }
        payload = {
            "model_id": "eleven_multilingual_v2",  # Replace with your model ID
            "text": text,
            "voice_settings": {
                "similarity_boost": 1,  # Set appropriate value
                "stability": 1,         # Set appropriate value
                "style": 1,             # Set appropriate value
                "use_speaker_boost": True
            }
        }
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        response = requests.post(url, params=query_params, json=payload, headers=headers, stream=True)
        if response.status_code == 200:
            # Streaming audio directly
            process = subprocess.Popen(["mpg123", "-"], stdin=subprocess.PIPE)
            for chunk in response.iter_content(chunk_size=1024):
                process.stdin.write(chunk)
            process.stdin.close()
            process.wait()
        else:
            print("Error in text-to-speech conversion:", response.text)
    else:
        # gTTS logic
        tts = gTTS(text=text, lang='en')  # You can change the language if needed
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            tts.save(temp_audio_file.name)
            subprocess.run(["mpg123", temp_audio_file.name])
            os.remove(temp_audio_file.name)  # Clean up the temporary file
def main():
    # Initialize conversation with a system message
    conversation_history.append({"role": "system", "content": openai_system_prompt})

    while True:
        audio = listen_for_speech()
        # Save the audio file if using Whisper
        if use_whisper_bool:
            with open("temp_audio.mp3", "wb") as audio_file:
                audio_file.write(audio.get_wav_data())
            prompt = transcribe_speech("temp_audio.mp3")
            os.remove("temp_audio.mp3")  # Clean up the temporary file
        else:
            prompt = transcribe_speech(audio)
        if prompt:
            response = query_chatgpt(prompt)
            if response:
                text_to_speech(response)

if __name__ == "__main__":
    main()

