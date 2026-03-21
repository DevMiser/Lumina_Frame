# The following program is provided by DevMiser - https://github.com/DevMiser

import base64
import datetime
import io
import json
import math
import numpy as np
import os
import pvporcupine
import pvkoala
import pyaudio
import queue
import sounddevice # this import suppresses abberant ALSA lib messages
import struct
import subprocess
import sys
import textwrap
import threading
import time
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from scipy.signal import savgol_filter
from websocket import create_connection, WebSocketConnectionClosedException

from google import genai
from google.genai import types
from google.api_core import exceptions

from PIL import Image

# ---Initialize Pygame

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
pygame.init()
pygame.mouse.set_visible(False) # Hide the cursor

# --- Lumina's Personality ---

LUMINA = ("""
    # Role & Identity
    - Your name is LooMa-Na.
    - You are a personable and helpful assistant.
    - You are concise and efficient.

    # Demeanor
    -Your demeanor should be welcoming, friendly, curious, and respectful.
    -Your demeanor should not be syncophatic, condescending or sarcastic.

    # Tone and Voice Style
    -Your tone and voice style should be authentic and polite.
    -Your tone and voice style should not be pompous or preachy.

    # Objectivity

    -Your responses should be honest, factual, intelligent, clear and concise.
    -Your responses should not be biased, repetitive, or ambiguous.

    # Enthusiasm Level
    - You should be calm and measured.
    - You should avoid rambling and excessive detail.

    # Filler Words
    -You should occasionally use filler words such as "um," "uh," or "hm," to sound more natural.
    -You should not start your response with 'sure', 'good question', 'great', 'absolutely', or any other obsequious statement.
    -You should not end your response with a question unless necessary for clarification.

    # Appearance
    -You have a visual display that shows a waveform that syncs to what you say.

    # Image Generation Capabilities
    - You can generate images when the user asks you to draw, paint, generate, create, or make
      a picture, image, painting, drawing, or schematic.
    - When the user requests an image, first briefly acknowledge their request (e.g., "I'll generate
      that for you"), then call the generate_image tool with a clear description.
    - After the image is generated, briefly confirm completion.
      Do not describe the image in excessive detail. It will auromatically be displayed on your screen.
    - If image generation fails, apologize briefly and suggest the user try again.

    # Image Saving
    - You can save the most recently generated image when the user asks to save, keep, or store it.
    - When saving, call the save_image tool and then announce the filename to the user.
    - If no image has been generated yet, let the user know there is nothing to save.

    # Screen Control
    - You can turn on the display to show the last generated image when the user asks to
      turn on the screen, show the image, display the picture, or light up the display.
      Call the show_screen tool. If no image exists, the logo will be shown.
    - You can turn off the display when the user asks to turn off the screen, blank the display,
      or shut off the monitor. Call the turn_off_display tool.
      The screen will turn off after your conversation ends.
      When the user asks to turn off the display, confirm that it will happen after you finish speaking.
    """
)

# --- API and Access Keys ---

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
PICOVOICE_ACCESS_KEY = os.environ["PICOVOICE_ACCESS_KEY"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

# --- Initialize Google Gemini client ---

client = genai.Client(api_key=GOOGLE_API_KEY)

# --- Audio and Streaming ---

CHUNK_SIZE = 2048
RATE = 24000
FORMAT = pyaudio.paInt16
INACTIVITY_TIMEOUT = 3   # Oracle times out after this many seconds of inactivity
SCREEN_BLANK_TIMEOUT = 600  # Screen blanks after 10 minutes of no wake-word activity

# --- Paths ---

LOGO_PATH = "/home/pi/Lumina/Lumina_Frame_Logo.png"
SAVE_PATH = "/home/pi/Lumina/Saved_Images"

# --- Aspect Ratio Selection ---

PERMITTED_ASPECT_RATIOS = [
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4",
    "4:1", "4:3", "4:5", "5:4", "8:1", "9:16",
    "16:9", "21:9"
]

def get_best_aspect_ratio(width, height):
    """Pick the permitted aspect ratio string closest to width/height."""
    screen_ratio = width / height
    best = None
    best_diff = float('inf')
    for ar in PERMITTED_ASPECT_RATIOS:
        w, h = ar.split(":")
        ratio = int(w) / int(h)
        diff = abs(screen_ratio - ratio)
        if diff < best_diff:
            best_diff = diff
            best = ar
    print(f"Screen {width}x{height} (ratio {screen_ratio:.4f}) -> best aspect ratio: {best}")
    return best

# --- Tool Helper and Functions ---

def blank_screen():
    os.system("xset dpms force off")

def generate_gemini_image(prompt):
    """Calls Gemini API to generate an image. Returns PIL Image or None."""
    print(f"Sending prompt to Gemini: {prompt}")

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                ),
                response_modalities=["IMAGE"]
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    raw_data = part.inline_data.data

                    try:
                        return Image.open(io.BytesIO(raw_data))
                    except Exception:
                        pass

                    try:
                        decoded_data = base64.b64decode(raw_data)
                        return Image.open(io.BytesIO(decoded_data))
                    except Exception as e:
                        print(f"Failed to decode image data: {e}")
                        return None

        print("No image found in the response candidates.")
        return None

    except exceptions.ResourceExhausted as e:
        print(f"Quota Error: {e.message}")
        return None
    except exceptions.ServiceUnavailable as e:
        print(f"Service Unavailable: {e}")
        return None
    except exceptions.Unauthenticated as e:
        print(f"Authentication Error: {e}")
        return None
    except Exception as e:
        print(f"Generation Error: {e}")
        return None

def get_current_time():
    """Returns the current date and time as a natural language string."""
    now = datetime.datetime.now()
    return now.strftime("The current date and time is %A, %B %d, %Y at %I:%M %p.")

def get_current_weather(location=None):
    """Fetches current weather from Open-Meteo for the given location.
    Defaults to Delray Beach, FL if no location is provided."""
    if not location:
        lat, lon = 26.4615, -80.0728
        location_display = "Delray Beach, Florida"
    else:
        try:
            geocode_url = (
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={urllib.parse.quote(location)}&count=1"
            )
            with urllib.request.urlopen(geocode_url, timeout=5) as resp:
                geo_data = json.loads(resp.read().decode())

            if not geo_data.get("results"):
                return f"Sorry, I couldn't find a location called {location}."

            result = geo_data["results"][0]
            lat = result["latitude"]
            lon = result["longitude"]
            name = result.get("name", location)
            admin1 = result.get("admin1", "")
            country = result.get("country", "")
            location_display = ", ".join(part for part in [name, admin1, country] if part)
        except Exception:
            return f"I wasn't able to look up the location {location}. Please try again."

    try:
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&temperature_unit=fahrenheit"
            f"&windspeed_unit=mph"
        )
        with urllib.request.urlopen(weather_url, timeout=5) as resp:
            weather_data = json.loads(resp.read().decode())

        cw = weather_data["current_weather"]
        temp = cw["temperature"]
        wind = cw["windspeed"]
        condition = _wmo_code_to_description(cw.get("weathercode", 0))

        return (
            f"The current weather in {location_display} is {condition}, "
            f"with a temperature of {temp} degrees Fahrenheit "
            f"and winds at {wind} miles per hour."
        )
    except Exception:
        return "I was unable to retrieve the weather right now. Please try again in a moment."

def save_generated_image(pil_image, prompt_label="image"):
    """Saves a PIL Image to disk. Returns the filename on success or error string."""
    if pil_image is None:
        return "No image to save."

    os.makedirs(SAVE_PATH, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    sanitized_label = prompt_label.replace(" ", "_")[:50]
    output_filename = f"{SAVE_PATH}{sanitized_label}_{timestamp}.png"

    try:
        pil_image.save(output_filename, format="PNG")
        print(f"Image saved as {output_filename}")
        return output_filename
    except Exception as e:
        error_msg = f"Failed to save image: {str(e)}"
        print(error_msg)
        return error_msg

def wake_screen():
    os.system("xset dpms force on")

def _wmo_code_to_description(code):
    """Converts a WMO weather interpretation code to a plain English description."""
    WMO_CODES = {
        0:  "clear sky",
        1:  "mainly clear",
        2:  "partly cloudy",
        3:  "overcast",
        45: "foggy",
        48: "icy fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "light snow",
        73: "moderate snow",
        75: "heavy snow",
        77: "snow grains",
        80: "light showers",
        81: "moderate showers",
        82: "heavy showers",
        85: "snow showers",
        86: "heavy snow showers",
        95: "thunderstorms",
        96: "thunderstorms with hail",
        99: "thunderstorms with heavy hail",
    }
    return WMO_CODES.get(code, "mixed conditions")

# --------------------------------------------------------------------------------
# Visualizer Class
# --------------------------------------------------------------------------------

class Visualizer:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        display_info = pygame.display.Info()
        self.WIDTH = display_info.current_w
        self.HEIGHT = display_info.current_h
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
#         self.WIDTH = 600
#         self.HEIGHT = 400
#         self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        os.system("xset s on && xset +dpms") # comment out this line to keep the display screen from sleeping
        pygame.display.set_caption("Lumina")

        global aspect_ratio
        aspect_ratio = get_best_aspect_ratio(self.WIDTH, self.HEIGHT)

        self.BACKGROUND = (0, 0, 0)
        self.WAVEFORM_COLOR = (0, 255, 158)
        self.TEXT_COLOR = (173, 216, 230)  # Light blue (#ADD8E6)

        self.font = pygame.font.Font(None, 74)
        self.text_font = pygame.font.SysFont("Arial Black", 36)

        self.audio_data = np.zeros(CHUNK_SIZE, dtype=np.float32)
        self.data_lock = threading.Lock()

        self.smoothing_window = 51
        self.smoothing_poly = 3
        self.silence_threshold = 0.01
        self.amplitude_scale = 1.5

        self.state = 'logo'
        self.running = False

        # Image display surfaces
        self.current_image_surface = None
        self.last_image_surface = None
        self.logo_surface = None

        # Persistent PIL image for saving across sessions
        self.last_generated_pil_image = None
        self.last_image_label = ""

        # Text display
        self.display_text_line1 = ""
        self.display_text_line2 = ""

    def load_logo(self):
        """Load and scale the logo image for pygame display."""
        try:
            pil_image = Image.open(LOGO_PATH)
            original_width, original_height = pil_image.size
            scale = max(self.WIDTH / original_width, self.HEIGHT / original_height)
            scaled_width = int(original_width * scale)
            scaled_height = int(original_height * scale)
            pil_image = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)

            if pil_image.mode == 'RGBA':
                # Convert RGBA to RGB with black background for pygame
                bg = Image.new('RGB', pil_image.size, (0, 0, 0))
                bg.paste(pil_image, mask=pil_image.split()[3])
                pil_image = bg
            elif pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            data = pil_image.tobytes()
            try:
                self.logo_surface = pygame.image.frombuffer(data, pil_image.size, 'RGB')
            except AttributeError:
                self.logo_surface = pygame.image.fromstring(data, pil_image.size, 'RGB')
            print(f"Logo loaded successfully from {LOGO_PATH}")
        except Exception as e:
            print(f"Could not load logo: {e}")
            self.logo_surface = None

    def display_logo(self):
        """Render the preloaded logo centered on black background."""
        self.screen.fill(self.BACKGROUND)
        if self.logo_surface:
            logo_rect = self.logo_surface.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(self.logo_surface, logo_rect)

    def set_image(self, pil_image, label=""):
        """Convert PIL Image to pygame surface, scale to fill screen, and store."""
        original_width, original_height = pil_image.size
        scale = max(self.WIDTH / original_width, self.HEIGHT / original_height)
        scaled_width = int(original_width * scale)
        scaled_height = int(original_height * scale)
        pil_resized = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)

        if pil_resized.mode == 'RGBA':
            bg = Image.new('RGB', pil_resized.size, (0, 0, 0))
            bg.paste(pil_resized, mask=pil_resized.split()[3])
            pil_resized = bg
        elif pil_resized.mode != 'RGB':
            pil_resized = pil_resized.convert('RGB')

        data = pil_resized.tobytes()
        try:
            surface = pygame.image.frombuffer(data, pil_resized.size, 'RGB')
        except AttributeError:
            surface = pygame.image.fromstring(data, pil_resized.size, 'RGB')

        self.current_image_surface = surface
        self.last_image_surface = surface
        self.last_generated_pil_image = pil_image
        self.last_image_label = label
        self.state = 'image'

    def display_image(self):
        """Render the current image surface centered on black background."""
        self.screen.fill(self.BACKGROUND)
        if self.current_image_surface:
            img_rect = self.current_image_surface.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(self.current_image_surface, img_rect)

    def set_text(self, line1, line2=""):
        """Set text to display and switch to text state."""
        self.display_text_line1 = line1
        self.display_text_line2 = line2
        self.state = 'text'

    def display_text(self):
        """Render text centered on black background with word wrapping for line2."""
        self.screen.fill(self.BACKGROUND)

        if self.display_text_line1:
            text_surface1 = self.text_font.render(self.display_text_line1, True, self.TEXT_COLOR)
            rect1 = text_surface1.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 4))
            self.screen.blit(text_surface1, rect1)

        if self.display_text_line2:
            wrapped = textwrap.fill(self.display_text_line2, width=50)
            lines = wrapped.split('\n')
            y_start = self.HEIGHT // 4 + 60
            for i, line in enumerate(lines):
                text_surface = self.text_font.render(line, True, self.TEXT_COLOR)
                rect = text_surface.get_rect(center=(self.WIDTH // 2, y_start + i * 50))
                self.screen.blit(text_surface, rect)

    def update_data(self, audio_bytes):
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        with self.data_lock:
            if len(samples) != len(self.audio_data):
                self.audio_data = np.zeros(len(samples), dtype=np.float32)
            self.audio_data[:] = samples

    def clear_to_black(self):
        self.screen.fill(self.BACKGROUND)

    def is_silent(self, data):
        return np.mean(np.abs(data)) < self.silence_threshold

    def generate_squiggle(self, length):
        noise = np.random.randn(length)
        window_length = 51
        if length < window_length:
            window_length = length if length % 2 != 0 else length - 1
        if window_length < 5:
            return np.zeros(length)
        smoothed_noise = savgol_filter(noise, window_length, 3)
        return smoothed_noise * 0.008

    def draw_waveform(self):
        self.screen.fill(self.BACKGROUND)
        with self.data_lock:
            current_data = self.audio_data.copy()

        try:
            smoothed_data = savgol_filter(current_data, self.smoothing_window, self.smoothing_poly)
        except ValueError:
            smoothed_data = current_data

        is_silent_flag = self.is_silent(smoothed_data)
        zero_y = (self.HEIGHT // 2) - 10
        points = []

        if is_silent_flag:
            squiggle = self.generate_squiggle(len(smoothed_data))
            for i, val in enumerate(squiggle):
                x = int(i * self.WIDTH / len(squiggle))
                y = int(zero_y + val * self.HEIGHT)
                points.append((x, y))
            if len(points) > 1:
                pygame.draw.lines(self.screen, self.WAVEFORM_COLOR, False, points, 6)
        else:
            for i, sample in enumerate(smoothed_data):
                x = int(i * self.WIDTH / len(smoothed_data))
                scaled_amplitude = sample * (self.HEIGHT / 2.5) * self.amplitude_scale
                y = int(zero_y + scaled_amplitude)
                points.append((x, y))
            if len(points) > 1:
                pygame.draw.lines(self.screen, self.WAVEFORM_COLOR, False, points, 3)

    def run(self):
        self.running = True
        self.load_logo()
        clock = pygame.time.Clock()
        while self.running:
            if self.state == 'blanked':
                time.sleep(1)
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            if self.state == 'visualizing':
                self.draw_waveform()
                pygame.display.flip()
                clock.tick(30)
            elif self.state == 'logo':
                self.display_logo()
                pygame.display.flip()
                clock.tick(10)
            elif self.state == 'text':
                self.display_text()
                pygame.display.flip()
                clock.tick(10)
            elif self.state == 'image':
                self.display_image()
                pygame.display.flip()
                clock.tick(10)
            else:
                self.clear_to_black()
                pygame.display.flip()
                clock.tick(10)
        pygame.quit()

    def stop(self):
        self.running = False

# --------------------------------------------------------------------------------
# Socket Class
# --------------------------------------------------------------------------------

class Socket:
    def __init__(self, api_key, ws_url):
        self.api_key = api_key
        self.ws_url = ws_url
        self.ws = None
        self.on_msg = None
        self._stop_event = threading.Event()
        self.lock = threading.Lock()

    def connect(self):
        self.ws = create_connection(
            self.ws_url,
            header=[f"Authorization: Bearer {self.api_key}"]
        )
        print("Connected to WebSocket.")
        threading.Thread(target=self._receive_messages, daemon=True).start()

    def _receive_messages(self):
        while not self._stop_event.is_set():
            try:
                raw = self.ws.recv()
                if raw and self.on_msg:
                    self.on_msg(json.loads(raw))
            except WebSocketConnectionClosedException:
                if not self._stop_event.is_set(): print("WebSocket closed by server.")
                break
            except Exception as e:
                if not self._stop_event.is_set(): print(f"Error: {e}")
        print("Receiver thread exiting.")

    def send(self, obj):
        try:
            with self.lock:
                if self.ws and self.ws.connected:
                    self.ws.send(json.dumps(obj))
        except Exception as e:
            print(f"Send error: {e}")

    def close(self):
        if not self._stop_event.is_set():
            self._stop_event.set()
            if self.ws:
                try:
                    self.ws.close()
                except Exception: pass
            print("WebSocket closed.")

# --------------------------------------------------------------------------------
# AUDIOIO Class
# --------------------------------------------------------------------------------

class AudioIO:
    def __init__(self, p_instance, visualizer_instance, porcupine, koala):
        self.audio_buffer = bytearray()
        self.mic_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.p = p_instance
        self.visualizer = visualizer_instance

        # Two-mode mic architecture
        self.porcupine = porcupine
        self.koala = koala
        self.mode = 'active'           # 'guarded' or 'active'
        self.mode_lock = threading.Lock()

        # Resampling and frame accumulation buffers for guarded mode
        self._resample_buf_16k = np.array([], dtype=np.int16)
        self._porcupine_buf = np.array([], dtype=np.int16)

        # Callbacks for wake-word and exit-word detection during session
        self.on_wake_word = None
        self.on_exit_word = None

    def _mic_cb(self, in_data, frame_count, time_info, status):
        self.mic_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def _spk_cb(self, in_data, frame_count, time_info, status):
        needed = frame_count * 2
        chunk = self.audio_buffer[:needed]
        self.audio_buffer = self.audio_buffer[needed:]

        if len(chunk) < needed:
            chunk += b"\x00" * (needed - len(chunk))

        self.visualizer.update_data(chunk)
        return (bytes(chunk), pyaudio.paContinue)

    def clear_buffer(self):
        """Instantly clears the audio buffer to stop AI speech."""
        self.audio_buffer = bytearray()

    def set_mode(self, mode):
        """Thread-safe mode switch between 'guarded' and 'active'."""
        with self.mode_lock:
            old_mode = self.mode
            self.mode = mode

        if mode == 'guarded' and old_mode == 'active':
            # Transitioning to guarded: reset Koala state (non-contiguous audio)
            # and clear resampling buffers
            self.koala.reset()
            self._resample_buf_16k = np.array([], dtype=np.int16)
            self._porcupine_buf = np.array([], dtype=np.int16)
            print(f"Audio mode: {old_mode} -> {mode}")

        elif mode == 'active' and old_mode == 'guarded':
            # Transitioning to active: drain mic queue to discard stale audio
            # so old audio doesn't get sent to OpenAI
            while not self.mic_queue.empty():
                try:
                    self.mic_queue.get_nowait()
                except queue.Empty:
                    break
            print(f"Audio mode: {old_mode} -> {mode}")

    def _process_guarded_audio(self, raw_24k_bytes):
        """Resample 24kHz mic audio to 16kHz, run Koala noise suppression,
        then feed enhanced audio to Porcupine for wake-word detection."""
        # Convert bytes to numpy int16 array
        samples_24k = np.frombuffer(raw_24k_bytes, dtype=np.int16)

        # Resample from 24kHz to 16kHz using linear interpolation
        num_out = int(len(samples_24k) * 16000 / 24000)
        if num_out == 0:
            return
        indices = np.linspace(0, len(samples_24k) - 1, num_out)
        samples_16k = np.interp(
            indices, np.arange(len(samples_24k)), samples_24k.astype(np.float64)
        ).astype(np.int16)

        # Accumulate resampled audio
        self._resample_buf_16k = np.concatenate([self._resample_buf_16k, samples_16k])

        # Process in Koala-sized frames, then feed results to Porcupine
        koala_fl = self.koala.frame_length

        while len(self._resample_buf_16k) >= koala_fl:
            koala_frame = self._resample_buf_16k[:koala_fl]
            self._resample_buf_16k = self._resample_buf_16k[koala_fl:]

            # Run noise suppression to remove speaker bleed
            enhanced = self.koala.process(koala_frame.tolist())

            # Accumulate enhanced audio for Porcupine
            self._porcupine_buf = np.concatenate([
                self._porcupine_buf,
                np.array(enhanced, dtype=np.int16)
            ])

        # Drain Porcupine-sized frames from the enhanced buffer
        porc_fl = self.porcupine.frame_length

        while len(self._porcupine_buf) >= porc_fl:
            porc_frame = self._porcupine_buf[:porc_fl]
            self._porcupine_buf = self._porcupine_buf[porc_fl:]

            keyword_index = self.porcupine.process(porc_frame.tolist())

            if keyword_index == 0:  # "Lumina" detected
                print("Wake word detected during session (guarded mode)")
                if self.on_wake_word:
                    self.on_wake_word()
            elif keyword_index == 1:  # "exit-the-program" detected
                print("Exit word detected during session (guarded mode)")
                if self.on_exit_word:
                    self.on_exit_word()

    def start_streams(self):
        self.in_stream = self.p.open(
            format=FORMAT, channels=1, rate=RATE,
            input=True, frames_per_buffer=CHUNK_SIZE, stream_callback=self._mic_cb,
        )
        self.out_stream = self.p.open(
            format=FORMAT, channels=1, rate=RATE,
            output=True, frames_per_buffer=CHUNK_SIZE, stream_callback=self._spk_cb
        )
        self.in_stream.start_stream()
        self.out_stream.start_stream()

    def stop_streams(self):
        self._stop_event.set()
        if hasattr(self, 'in_stream'):
            self.in_stream.stop_stream()
            self.in_stream.close()
        if hasattr(self, 'out_stream'):
            self.out_stream.stop_stream()
            self.out_stream.close()

    def send_mic(self, sock):
        while not self._stop_event.is_set():
            try:
                data = self.mic_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            with self.mode_lock:
                current_mode = self.mode

            if current_mode == 'active':
                # Mode B: send audio to Realtime API (normal behavior)
                enc = base64.b64encode(data).decode()
                sock.send({"type": "input_audio_buffer.append", "audio": enc})
            else:
                # Mode A (guarded): run wake-word detection locally
                self._process_guarded_audio(data)

    def push_back(self, audio_bytes):
        self.audio_buffer.extend(audio_bytes)

# --------------------------------------------------------------------------------
# Realtime Class
# --------------------------------------------------------------------------------

class Realtime:
    def __init__(self, api_key, ws_url, p_instance, visualizer_instance, porcupine, koala):
        self.sock = Socket(api_key, ws_url)
        self.audio = AudioIO(p_instance, visualizer_instance, porcupine, koala)
        self.sent_update = False
        self._stop_event = threading.Event()
        self.user_speaking = False
        self.visualizer = visualizer_instance
        self.generating_image = False
        self.ai_responding = False
        self.exit_requested = False
        self.pending_active_switch = False
        self.new_image_this_session = False
        self.screen_on_requested = False
        self.screen_off_requested = False

    def start(self):
        self.sock.on_msg = self.on_msg
        self.sock.connect()
        self.audio.on_wake_word = self._handle_wake_word_interrupt
        self.audio.on_exit_word = self._handle_exit_word
        self.audio.set_mode('active')  # User just said "Lumina", expect speech
        self.audio.start_streams()
        threading.Thread(target=self.audio.send_mic, args=(self.sock,), daemon=True).start()

    def _handle_wake_word_interrupt(self):
        """Called when wake word is detected during an active session (guarded mode)."""
        print("Lumina detected - interrupting AI and switching to active mode")

        # Clear any playing AI audio
        self.audio.clear_buffer()

        # Cancel any in-progress response from the API
        self.sock.send({"type": "response.cancel"})

        # Clear OpenAI's input audio buffer (discard stale audio from before the wake word)
        self.sock.send({"type": "input_audio_buffer.clear"})

        # Switch to active mode - start sending mic audio to Realtime API
        self.audio.set_mode('active')

    def _handle_exit_word(self):
        """Called when 'exit-the-program' is detected during a session."""
        print("Exit word detected during session - flagging for shutdown")
        self.exit_requested = True

    def on_msg(self, msg):
        typ = msg.get("type")

        if typ not in ("response.output_audio.delta", "response.output_audio_transcript.delta", "rate_limits.updated"):
            print(f"Event: {typ}")

        if typ == "session.created" and not self.sent_update:
            self.sent_update = True
            print("Session created. Sending session update (Server VAD)...")

            # Build instructions, adding image context if one is currently displayed
            instructions = LUMINA
            if self.visualizer.last_generated_pil_image is not None:
                instructions += (
                    "\n\n# Current State\n"
                    "- An image is currently available from a previous interaction.\n"
                    f"- The image was generated with the prompt: '{self.visualizer.last_image_label}'\n"
                    "- If the user asks to save the image, call the save_image tool.\n"
                    "- If the user asks to show the image or turn on the screen, call the show_screen tool."
                )

            self.sock.send({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "instructions": instructions,
                    "tools": [
                        {
                            "type": "function",
                            "name": "get_current_time",
                            "description": "Returns the current date and time.",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "get_current_weather",
                            "description": (
                                "Gets the current weather conditions for a location. "
                                "Defaults to Delray Beach, Florida if no location is provided."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "The city or location name to get weather for. "
                                            "Pass null to use the default location of Delray Beach, Florida."
                                        )
                                    }
                                },
                                "required": ["location"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "generate_image",
                            "description": (
                                "Generates an image based on the user's description using AI image generation. "
                                "Call this when the user asks you to draw, paint, generate, create, or make "
                                "a picture, image, painting, drawing, or schematic. "
                                "Pass the user's description as the prompt. "
                                "Before calling this tool, tell the user you will generate the image for them."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "prompt": {
                                        "type": "string",
                                        "description": (
                                            "A detailed description of the image to generate. "
                                            "Use the user's words, expanding slightly for clarity if needed."
                                        )
                                    }
                                },
                                "required": ["prompt"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "save_image",
                            "description": (
                                "Saves the most recently generated image to disk. "
                                "Call this when the user asks to save, keep, or store the current image."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "show_screen",
                            "description": (
                                "Turns on the display and shows the most recently generated image. "
                                "Call this when the user asks to turn on the screen, show the image, "
                                "display the picture, or light up the display. "
                                "If no image has been generated, the logo will be shown instead."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "turn_off_display",
                            "description": (
                                "Turns off the display after the current conversation ends. "
                                "Call this when the user asks to turn off the screen, blank the display, "
                                "or shut off the monitor. The screen will remain on during the conversation "
                                "but will turn off once the session ends."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": [],
                                "additionalProperties": False
                            }
                        }
                    ],
                    "tool_choice": "auto",
                    "audio": {
                        "input": {
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": 0.8,
                                "silence_duration_ms": 550,
                                "prefix_padding_ms": 180
                            }
                        },
                        "output": {
                            "voice": "marin"
                        }
                    }
                }
            })

        # --- Speech events ---
        # Only act on speech detection in active mode. Only the wake word can
        # interrupt in guarded mode.
        elif typ == "input_audio_buffer.speech_started":
            with self.audio.mode_lock:
                current_mode = self.audio.mode
            if current_mode == 'active':
                print("User started speaking (active mode)")
                self.user_speaking = True
                if len(self.audio.audio_buffer) > 0:
                    self.audio.clear_buffer()
                    self.sock.send({"type": "response.cancel"})
            else:
                print("Speech detected but ignoring (guarded mode)")

        elif typ == "input_audio_buffer.speech_stopped":
            with self.audio.mode_lock:
                current_mode = self.audio.mode
            if current_mode == 'active':
                print("User stopped speaking")
                self.user_speaking = False

        # --- Response lifecycle for mode switching ---
        # Switch to guarded when AI starts responding (protects from
        # bystander speech interrupting while AI is talking)
        elif typ == "response.created":
            self.ai_responding = True
            self.audio.set_mode('guarded')
            # Clear any stale audio in OpenAI's input buffer to prevent
            # residual audio from triggering speech detection
            self.sock.send({"type": "input_audio_buffer.clear"})

        elif typ == "response.done":
            response_obj = msg.get("response", {})
            status = response_obj.get("status", "")
            output = response_obj.get("output", [])

            # Check if this response contains a function call
            # (the model will respond again after tool execution)
            has_function_call = any(
                item.get("type") == "function_call" for item in output
            )

            print(f"Response complete (status={status}, has_tool_call={has_function_call})")

            if status == "completed" and not has_function_call:
                # AI finished sending audio, but the local audio_buffer
                # may still be playing through the speaker. Stay in guarded
                # mode until the buffer drains to prevent speaker bleed or
                # user speech from triggering a false interruption.
                # The main loop will switch to active once the buffer is empty.
                self.ai_responding = False
                self.pending_active_switch = True
            elif status == "cancelled":
                # Response was cancelled (by wake word interrupt)
                # Stay in active mode - user is about to speak
                self.ai_responding = False
            else:
                # Tool call in progress or other status - stay in current mode
                self.ai_responding = False

        # --- Audio Playback ---
        elif typ == "response.output_audio.delta":
            data = base64.b64decode(msg["delta"])
            self.audio.push_back(data)

        elif typ == "response.function_call_arguments.done":
            call_id = msg.get("call_id")
            func_name = msg.get("name")
            raw_args = msg.get("arguments", "{}")
            print(f"Tool call: {func_name}  args={raw_args}")
            threading.Thread(
                target=self._execute_tool,
                args=(call_id, func_name, raw_args),
                daemon=True
            ).start()

        elif typ == "error":
            print(f"Server error: {msg.get('error')}")

    def _execute_tool(self, call_id, func_name, raw_args):
        """Executes a tool function and sends the result back to the Realtime API."""
        if not call_id:
            print("Tool call received with no call_id, skipping.")
            return

        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {}

        try:
            if func_name == "get_current_time":
                output = get_current_time()

            elif func_name == "get_current_weather":
                output = get_current_weather(args.get("location", None))

            elif func_name == "generate_image":
                prompt = args.get("prompt", "")
                self.generating_image = True

                try:
                    self.visualizer.set_text("Generating new image...", prompt)
                    print(f"Generating image for: {prompt}")

                    pil_image = generate_gemini_image(prompt)

                    if pil_image:
                        self.visualizer.set_image(pil_image, prompt)
                        self.new_image_this_session = True
                        output = f"Image generated successfully for prompt: {prompt}"
                        print("Image generated and displayed.")
                    else:
                        self.visualizer.set_text("Image generation failed.", "Please try again.")
                        output = "Image generation failed. The API returned no image. Tell the user to try again."

                except exceptions.ResourceExhausted:
                    self.visualizer.set_text("Rate limit reached.", "Please wait and try again.")
                    output = "Image generation failed due to API rate limiting. Tell the user to wait a moment and try again."

                except exceptions.ServiceUnavailable:
                    self.visualizer.set_text("Service unavailable.", "Check network connection.")
                    output = "Image generation failed because the service is unavailable. Tell the user to check the network connection."

                except exceptions.Unauthenticated:
                    self.visualizer.set_text("API key invalid.", "Check configuration.")
                    output = "Image generation failed due to an invalid API key."

                except Exception as e:
                    error_msg = str(e)
                    self.visualizer.set_text("An error occurred.", error_msg[:80])
                    output = f"Image generation failed with error: {error_msg}"

                finally:
                    self.generating_image = False

            elif func_name == "save_image":
                if self.visualizer.last_generated_pil_image is not None:
                    filename = save_generated_image(self.visualizer.last_generated_pil_image, self.visualizer.last_image_label)
                    if filename.startswith("/"):
                        self.visualizer.set_text("Image saved!", filename)
                        output = f"Image saved successfully as {filename}"
                    else:
                        output = filename
                else:
                    output = "No image has been generated yet to save."

            elif func_name == "show_screen":
                self.screen_on_requested = True
                if self.visualizer.last_image_surface is not None:
                    self.visualizer.current_image_surface = self.visualizer.last_image_surface
                    self.visualizer.state = 'image'
                    output = "The display is now showing the most recent image."
                else:
                    self.visualizer.state = 'logo'
                    output = "The display is now on. No image has been generated yet, so the logo is shown."

            elif func_name == "turn_off_display":
                self.screen_off_requested = True
                output = (
                    "The display will turn off when the conversation ends. "
                    "Let the user know the screen will go dark after you finish speaking."
                )

            else:
                output = f"Unknown function: {func_name}"

        except Exception as e:
            output = f"An error occurred while executing {func_name}: {str(e)}"

        print(f"Tool result: {output}")

        self.sock.send({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output
            }
        })
        self.sock.send({"type": "response.create"})

    def stop(self):
        self._stop_event.set()
        self.audio.stop_streams()
        self.sock.close()
        print("Realtime session stopped.")
        print("\nListening for wake word...")

def main():
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-1.5"
    visualizer, porcupine, pa = None, None, None
    koala = None
    audio_stream = None
    
    # --- Adust Microphone Gain in ALSA Mixer ---

    subprocess.run(["amixer", "-c", "1", "set", "Mic", "52%"]) 

    try:
        visualizer = Visualizer()
        viz_thread = threading.Thread(target=visualizer.run, daemon=True)
        viz_thread.start()
        time.sleep(0.5)

        # Initialize Porcupine (Wake Word)
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keywords=['Lumina', 'exit-the-program'],
            sensitivities=[0.2, 0.3]
        )

        pa = pyaudio.PyAudio()

        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )

        print("Listening for wake word...")

        pcm_format = "h" * porcupine.frame_length

        last_interaction_time = time.time()
        screen_blanked = False

        while True:
            try:

                # Check if screen should be blanked due to inactivity
                if not screen_blanked and time.time() - last_interaction_time > SCREEN_BLANK_TIMEOUT:
                    blank_screen()
                    screen_blanked = True
                    visualizer.state = 'blanked'
                    print("Screen blanked due to inactivity.")

                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)

                pcm_unpacked = struct.unpack_from(pcm_format, pcm)
                keyword_index = porcupine.process(pcm_unpacked)

                if keyword_index == 1:
                    print("\nExit the Program detected")
                    time.sleep(0.5)
                    break

                if keyword_index == 0:
                    print("\nWake word detected")

                    # Capture whether screen was blanked before waking
                    was_blanked_at_wake = screen_blanked

                    if screen_blanked:
                        wake_screen()
                        screen_blanked = False
                        # Restore display to image or logo
                        if visualizer.last_image_surface is not None:
                            visualizer.current_image_surface = visualizer.last_image_surface
                            visualizer.state = 'image'
                        else:
                            visualizer.state = 'logo'
                        print("Screen woken by wake word.")

                    # Close the wake-word stream to free up the mic
                    if audio_stream.is_active():
                        audio_stream.stop_stream()
                        audio_stream.close()

                    # Create Koala for noise suppression during this session only
                    koala = pvkoala.create(access_key=PICOVOICE_ACCESS_KEY)
                    print(f"Koala initialized (sample_rate={koala.sample_rate}, frame_length={koala.frame_length})")

                    # Start the Realtime Session with Porcupine and Koala
                    rt_session = Realtime(OPENAI_API_KEY, url, pa, visualizer, porcupine, koala)

                    try:
                        rt_session.start()
                        visualizer.state = 'visualizing'
                        last_activity_time = time.time()

                        while True:
                            ai_is_talking = len(rt_session.audio.audio_buffer) > 0
                            user_is_talking = rt_session.user_speaking

                            if user_is_talking or ai_is_talking:
                                last_activity_time = time.time()

                            # Switch to active mode only after the audio buffer
                            # has fully drained (speaker finished playing).
                            # This prevents speaker bleed or user speech from
                            # triggering a false interruption via OpenAI's VAD.
                            if rt_session.pending_active_switch and not ai_is_talking:
                                rt_session.pending_active_switch = False
                                rt_session.audio.set_mode('active')
                                last_activity_time = time.time()

                            # Suppress timeout while generating image
                            if rt_session.generating_image:
                                last_activity_time = time.time()

                            # Check if exit word was detected during session
                            if rt_session.exit_requested:
                                print("Exit requested during session. Shutting down.")
                                rt_session.stop()
                                if visualizer is not None:
                                    visualizer.stop()
                                if koala is not None:
                                    koala.delete()
                                if porcupine is not None:
                                    porcupine.delete()
                                if pa is not None:
                                    pa.terminate()
                                print("Cleanup complete.")
                                return

                            if time.time() - last_activity_time > INACTIVITY_TIMEOUT:
                                print("Inactivity timeout reached. Closing session.")
                                break
                            time.sleep(0.1)

                    except Exception as e:
                        print(f"Failed to start or run session: {e}")

                    finally:
                        # Read session flags before stopping
                        screen_off = rt_session.screen_off_requested
                        new_image = rt_session.new_image_this_session
                        screen_on = rt_session.screen_on_requested

                        rt_session.stop()

                        # Release Koala to stop billing
                        if koala is not None:
                            koala.delete()
                            koala = None
                            print("Koala released.")

                        # --- Post-session screen behavior (priority order) ---
                        if screen_off:
                            # User asked to turn off the display
                            print("Screen off requested. Blanking screen.")
                            blank_screen()
                            screen_blanked = True
                            visualizer.state = 'blanked'
                        elif new_image or screen_on:
                            # New image generated OR user asked to show screen
                            print("Showing image/logo, restarting blank timer.")
                            if visualizer.last_image_surface is not None:
                                visualizer.current_image_surface = visualizer.last_image_surface
                                visualizer.state = 'image'
                            else:
                                visualizer.state = 'logo'
                            last_interaction_time = time.time()
                        elif was_blanked_at_wake:
                            # Woke from blank, no new image or screen commands
                            print("Was blanked at wake with no new image. Re-blanking.")
                            blank_screen()
                            screen_blanked = True
                            visualizer.state = 'blanked'
                        else:
                            # Default: screen was on, no special commands
                            if visualizer.last_image_surface is not None:
                                visualizer.current_image_surface = visualizer.last_image_surface
                                visualizer.state = 'image'
                            else:
                                visualizer.state = 'logo'
                            last_interaction_time = time.time()

                        # Re-open the wake-word stream for the next loop
                        audio_stream = pa.open(
                            rate=porcupine.sample_rate,
                            channels=1,
                            format=pyaudio.paInt16,
                            input=True,
                            frames_per_buffer=porcupine.frame_length
                        )

            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(0.1)
                if audio_stream is None or not audio_stream.is_active():
                     audio_stream = pa.open(
                        rate=porcupine.sample_rate,
                        channels=1,
                        format=pyaudio.paInt16,
                        input=True,
                        frames_per_buffer=porcupine.frame_length
                    )

    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting.")

    finally:
        if audio_stream is not None:
            audio_stream.close()
        if pa is not None:
            pa.terminate()
        if koala is not None:
            koala.delete()
        if porcupine is not None:
            porcupine.delete()
        if visualizer is not None:
            visualizer.stop()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
