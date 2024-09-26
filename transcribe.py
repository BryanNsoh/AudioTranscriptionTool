import os
import pyaudio
import wave
import tempfile
from groq import Groq
from dotenv import dotenv_values
import time
import sys
import keyboard
import pyperclip
import pyautogui
import threading
import random
import pystray
from PIL import Image, ImageDraw

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), ".env")
env_vars = dotenv_values(env_path)

# Check for API key
GROQ_API_KEY = env_vars.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY not found in .env file.")
    print("Make sure you have a .env file in the same directory as this script with the line:")
    print("GROQ_API_KEY=your_api_key_here")
    sys.exit(1)
else:
    print("GROQ_API_KEY loaded successfully.")

# Global variables
recording = False
transcribing = False
audio_frames = []
hotkey = 'ctrl+alt+shift+r'  # Define a unique global hotkey

# Function to create simple colored icons
def create_icon(color):
    # Create a 64x64 image with transparent background
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Draw a filled circle
    draw.ellipse((8, 8, 56, 56), fill=color)
    return image

# Define tray icons
icon_idle = create_icon('grey')    # Idle state
icon_recording = create_icon('red')  # Recording state

# Initialize tray icon with idle state
tray_icon = None

def record_audio():
    global recording, audio_frames
    chunk = 1024
    format = pyaudio.paInt16
    channels = 1
    rate = 16000

    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=format,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk
        )
    except Exception as e:
        print(f"Failed to open audio stream: {e}")
        sys.exit(1)

    while True:
        if recording:
            try:
                data = stream.read(chunk)
                audio_frames.append(data)
            except Exception as e:
                print(f"Error reading audio stream: {e}")
                recording = False
                update_tray_icon(idle=True)
        else:
            time.sleep(0.1)  # Sleep to reduce CPU usage when not recording

def save_audio_to_temp():
    global audio_frames
    if not audio_frames:
        print("No audio frames to save.")
        return None

    try:
        filename = tempfile.mktemp(suffix=".wav")
        wf = wave.open(filename, "wb")
        wf.setnchannels(1)
        wf.setsampwidth(pyaudio.PyAudio().get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b"".join(audio_frames))
        wf.close()
        print(f"Audio saved to temporary file: {filename}")
        return filename
    except Exception as e:
        print(f"Failed to save audio: {e}")
        return None

def transcribe_audio(filename):
    client = Groq(api_key=GROQ_API_KEY)
    max_retries = 5
    max_delay = 120  # 2 minutes in seconds

    for attempt in range(max_retries):
        try:
            with open(filename, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(filename), file.read()),
                    model="whisper-large-v3",
                    response_format="text",
                )
            print("Transcription successful.")
            return transcription, True
        except Exception as e:
            print(f"Transcription attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                delay = min(2**attempt + random.uniform(0, 1), max_delay)
                print(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                print(f"All transcription attempts failed: {e}")
                return f"Transcription failed after {max_retries} attempts: {str(e)}", False

def toggle_recording():
    global recording, audio_frames, transcribing
    if transcribing:
        print("Transcription in progress. Please wait.")
        return

    recording = not recording
    if recording:
        print("Recording started.")
        audio_frames = []  # Clear previous frames
        update_tray_icon(idle=False)
    else:
        print("Recording stopped. Starting transcription.")
        update_tray_icon(idle=True)
        transcribing = True
        temp_audio_file = save_audio_to_temp()
        if temp_audio_file:
            transcription, success = transcribe_audio(temp_audio_file)
            if success:
                pyperclip.copy(transcription)
                # Simulate paste operation
                time.sleep(0.5)  # Brief pause to ensure clipboard is updated
                pyautogui.hotkey('ctrl', 'v')
                os.remove(temp_audio_file)
                print("Transcription copied to clipboard and pasted.")
            else:
                os.remove(temp_audio_file)
                print("Transcription failed.")
        transcribing = False

def update_tray_icon(idle=True):
    if idle:
        tray_icon.icon = icon_idle
    else:
        tray_icon.icon = icon_recording

def on_quit(icon, item):
    icon.stop()
    os._exit(0)  # Force exit all threads

def setup_tray():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem('Quit', on_quit)
    )
    tray_icon = pystray.Icon("AudioTranscriptionTool", icon_idle, "Audio Transcription Tool", menu)
    tray_icon.run()

def main():
    # Start the recording thread
    recording_thread = threading.Thread(target=record_audio, daemon=True)
    recording_thread.start()
    print("Recording thread started.")

    # Register the global hotkey
    try:
        keyboard.add_hotkey(hotkey, toggle_recording)
        print(f"Global hotkey '{hotkey}' registered.")
    except Exception as e:
        print(f"Failed to register hotkey '{hotkey}': {e}")
        sys.exit(1)

    # Setup the system tray icon in a separate thread
    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()
    print("System tray icon setup complete.")

    print("Audio Transcription Tool is running in the background.")
    print(f"Press the global hotkey '{hotkey}' to start/stop recording.")
    print("Right-click the tray icon and select 'Quit' to exit the application.")

    try:
        while True:
            time.sleep(1)  # Keep the main thread alive
    except KeyboardInterrupt:
        print("Exiting Audio Transcription Tool.")
        sys.exit(0)

if __name__ == "__main__":
    main()
