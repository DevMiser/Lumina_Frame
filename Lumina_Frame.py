# The following program is provided by DevMiser - https://github.com/DevMiser

import base64
import datetime
import difflib
import io
import json
import math
import numpy as np
import os
import random
import pvporcupine
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

    # Demeanor
    - Be welcoming, friendly, curious, and respectful.
    - Be concise and efficient.
    - Do not be syncophatic, condescending or sarcastic.

    # Tone and Voice Style

    - Use a tone and voice style that is authentic and polite.
    - Do not use a tone or voice style that is pompous or preachy.

    # Objectivity

    - Be honest, factual, intelligent, clear and concise.
    - Do not be biased, repetitive, or ambiguous.

    # Enthusiasm Level
    - Keep your entusiasm level calm and measured unless requested otherwise.
    - Avoid rambling and excessive detail.

    # Filler Words
    - Occasionally use filler words such as "um," "uh," or "hm," to sound more natural.
    - Do not not start your response with 'sure', 'good question', 'great', 'absolutely', or any other obsequious statement.
    - Do not end your response with a question unless necessary for clarification.

    # Appearance
    - You have a visual display that shows a waveform that syncs to what you say.

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
    - You can show the logo by calling the show_logo tool when the user asks to
      show the logo, display the start screen, show the home screen, or similar.
    - You can turn off the display when the user asks to turn off the screen, blank the display,
      or shut off the monitor. Call the turn_off_display tool.
      The screen will turn off immediately. Your voice will still be audible.
    - When the user asks to turn off the display, confirm that it is done.

    # Always-On Display
    - The display stays on automatically from 8:00 AM to 9:00 PM when always-on mode is enabled.
    - If the user asks to turn off the display during these hours, it will stay off
      until the next always-on cycle or until they ask to turn it back on.
    - The user can enable or disable the always-on feature by asking you to
      turn always-on mode on or off. Call the set_always_on tool with enabled
      set to true or false accordingly.
    - When toggling always-on mode, confirm the new state to the user.

    # Listing Saved Images
    - You can list the subjects of saved images when the user asks what images have been
      saved, what pictures you have, or to tell them about saved images.
      Call the list_saved_images tool.
    - When reporting the results, describe the subjects naturally (e.g., "We have a sunset,
      a cat playing piano, and a mountain landscape") rather than reading raw filenames.
    - The tool returns a random sample of 3 or 4 subjects. After listing them, let the
      user know how many total images are saved and ask if they'd like to hear more.

    # Image Recall
    - You can find and retrieve previously saved images when the user asks to
      recall, find, or look up a saved picture, image, or painting.
    - When the user asks to find a saved image, call the recall_image tool with
      the key descriptive words from their request.
    - If a match is found, the image will be displayed automatically. Briefly confirm
      what image was found. Do not describe the image in excessive detail.
    - If no match is found, let the user know that no saved image matched their
      description, and suggest they try different words.
    - Important: The recall_image tool is only for finding saved images by description.
      It is not for turning the screen on or off. Use show_screen and turn_off_display
      for screen control.

    # Weather
    - For current conditions, use get_current_weather. For tomorrow or a future day, use get_weather_forecast.
    - If the user does not mention a specific location, call the weather tool immediately with
      location=null — do NOT ask the user to confirm or name a location first.

    # Timers
    - You can set named countdown timers using the set_timer tool.
    - You can cancel a running timer with cancel_timer and check remaining time with get_timer_status.
    - When a timer finishes, you will be notified via a system message and should announce it to the user.
    - If the user asks to set a timer without a specific name, use 'timer' as the label.
    """
)

# --- API and Access Keys ---

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
PICOVOICE_ACCESS_KEY = os.environ["PICOVOICE_ACCESS_KEY"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
OPENWEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]

# --- Default weather location (overwritten by IP geolocation at startup if USE_IP_LOCATION=True) ---

DEFAULT_WEATHER_Q        = "New York,NY,US"
DEFAULT_LOCATION_DISPLAY = "New York, NY"
USE_IP_LOCATION          = True

# --- Initialize Google Gemini client ---

client = genai.Client(api_key=GOOGLE_API_KEY)

# --- Audio and Streaming ---

CHUNK_SIZE = 2048
RATE = 24000
FORMAT = pyaudio.paInt16
INACTIVITY_TIMEOUT = 3   # Oracle times out after this many seconds of inactivity
SCREEN_BLANK_TIMEOUT = 600  # Screen blanks after 10 minutes of no wake-word activity unless Always_On is enabled

# --- Always-On Display Schedule ---

ALWAYS_ON_ENABLED = True
ALWAYS_ON_START_HOUR = 8    # 8:00 AM
ALWAYS_ON_END_HOUR = 21     # 9:00 PM

# --- ALSA Volume Helpers ---

def _set_alsa_capture(gain_pct: int) -> bool:
    """Set ALSA microphone capture volume. Typical range: 0–100."""
    try:
        result = subprocess.run(
            ["amixer", "-c", "1", "-q", "sset", "Mic", f"{gain_pct}%"],
            check=False, timeout=1
        )
        return result.returncode == 0
    except Exception as e:
        print(f"amixer error: {e}")
        return False

def _set_alsa_playback(vol_pct: int) -> bool:
    """Set ALSA speaker playback volume."""
    try:
        result = subprocess.run(
            ["amixer", "-c", "1", "-q", "sset", "PCM", f"{vol_pct}%"],
            check=False, timeout=1
        )
        return result.returncode == 0
    except Exception as e:
        print(f"amixer error: {e}")
        return False

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

# --- Chime (fallback when a timer fires after the session ends) ---

# Shared PyAudio instance set by main() at startup so _play_chime can open
# an output stream without spawning a separate process that would conflict
# with the already-open Porcupine input stream.
_pa_instance = None

def _play_chime():
    """Play a short 880 Hz beep three times (1-second apart) using PyAudio.
    Used when a timer fires after the session ends."""
    if _pa_instance is None:
        print("Chime: PyAudio instance not available.")
        return

    sample_rate = RATE   # 24000 Hz — same rate the device already handles
    freq = 880
    duration = 0.8
    num_samples = int(sample_rate * duration)
    raw = bytearray()
    for i in range(num_samples):
        val = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        fade = min(1.0, (num_samples - i) / (sample_rate * 0.1))
        raw += struct.pack('<h', int(val * fade))
    tone = bytes(raw)

    for i in range(3):
        if i > 0:
            time.sleep(1.0)
        try:
            stream = _pa_instance.open(
                format=FORMAT,
                channels=1,
                rate=sample_rate,
                output=True,
            )
            stream.write(tone)
            stream.stop_stream()
            stream.close()
        except Exception as e:
            print(f"Chime error: {e}")
            break

# --- Persistent timer state (survives inactivity timeouts / session restarts) ---
# Stored here at module level so a new Realtime session can see timers set in a previous one.

_timers = {}              # label -> {"timer": threading.Timer, "start": float, "duration": float}
_timers_lock = threading.Lock()

# Reference to the currently active Realtime session.  _fire_timer uses this so it
# always announces through whichever session is open at the moment the timer expires.
_active_session = None
_active_session_lock = threading.Lock()

def _fire_timer(label):
    """Called by threading.Timer when a countdown expires.
    Announces through the currently active session (if any) or falls back to a chime and display."""
    with _timers_lock:
        _timers.pop(label, None)

    with _active_session_lock:
        session = _active_session

    session_live = (
        session is not None
        and not session._stop_event.is_set()
        and session.sock.ws is not None
        and session.sock.ws.connected
    )

    if session_live:
        print(f"Timer '{label}' fired — announcing via active session.")
        if len(session.audio.audio_buffer) > 0:
            session.audio.clear_buffer()
            session.sock.send({"type": "response.cancel"})
        session.sock.send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": f"[System: The '{label}' timer has finished. Please announce this to the user.]"
                }]
            }
        })
        session.sock.send({"type": "response.create"})
    else:
        print(f"Timer '{label}' fired — no active session, playing chime.")
        threading.Thread(target=_play_chime, daemon=True).start()
        if viz is not None:
            viz.set_text("Timer Finished", f"The '{label}' timer has finished.")

            def _revert_after_finish():
                time.sleep(3)
                if viz is None:
                    return
                with _timers_lock:
                    any_timers = bool(_timers)
                if viz.state == 'text':
                    viz.state = 'countdown' if any_timers else (viz.pre_countdown_state or 'logo')

            threading.Thread(target=_revert_after_finish, daemon=True).start()

# --- Tool Helper and Functions ---

def is_always_on_hours():
    """Returns True if current time is within the always-on display window."""
    if not ALWAYS_ON_ENABLED:
        return False
    now = datetime.datetime.now()
    return ALWAYS_ON_START_HOUR <= now.hour < ALWAYS_ON_END_HOUR

def set_always_on(enabled):
    """Enable or disable the always-on display feature."""
    global ALWAYS_ON_ENABLED
    ALWAYS_ON_ENABLED = enabled
    state = "enabled" if enabled else "disabled"
    print(f"Always-on display mode {state}.")
    return f"Always-on display mode has been {state}. " + (
        f"The screen will stay on from {ALWAYS_ON_START_HOUR}:00 AM to {ALWAYS_ON_END_HOUR - 12}:00 PM."
        if enabled else
        "The screen will now follow the normal inactivity timeout."
    )

def _backlight_path():
    """Return the first sysfs backlight brightness path, or None."""
    try:
        entries = os.listdir("/sys/class/backlight")
        if entries:
            return f"/sys/class/backlight/{entries[0]}/brightness"
    except OSError:
        pass
    return None

_bl_path = None   # cached on first call


def blank_screen():
    global _bl_path
    if _bl_path is None:
        _bl_path = _backlight_path() or ""

    if _bl_path:
        try:
            with open(_bl_path, "w") as f:
                f.write("0")
            return
        except OSError:
            pass

    # Fallback: disable compositor output via wlr-randr (install: sudo apt install wlr-randr)
    if os.system("wlr-randr --output DSI-1 --off 2>/dev/null") != 0:
        os.system("vcgencmd display_power 0 1")

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
    """Fetches current weather from OpenWeather for the given location.
    Defaults to the device's detected location if no location is provided."""
    if not location:
        q = DEFAULT_WEATHER_Q
        location_display = DEFAULT_LOCATION_DISPLAY
    else:
        q = location
        location_display = None   # will be filled from the API response

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={urllib.parse.quote(q)}"
            f"&units=imperial"
            f"&appid={OPENWEATHER_API_KEY}"
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if location_display is None:
            city    = data.get("name", q)
            country = data.get("sys", {}).get("country", "")
            location_display = f"{city}, {country}" if country else city

        temp      = round(data["main"]["temp"])
        wind      = round(data["wind"]["speed"])
        condition = data["weather"][0]["description"]

        return (
            f"The current weather in {location_display} is {condition}, "
            f"with a temperature of {temp} degrees Fahrenheit "
            f"and winds at {wind} miles per hour."
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Sorry, I couldn't find weather data for '{location or DEFAULT_LOCATION_DISPLAY}'."
        return "I was unable to retrieve the weather right now. Please try again in a moment."
    except Exception:
        return "I was unable to retrieve the weather right now. Please try again in a moment."

def _resolve_forecast_date(date_str):
    """Resolve a date string to a datetime.date object.
    Accepts: None/'tomorrow', a weekday name, or an ISO 'YYYY-MM-DD' string.
    Returns (date, error_string).  error_string is None on success."""
    today    = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    if not date_str or date_str.strip().lower() == "tomorrow":
        return tomorrow, None

    ds = date_str.strip().lower()

    # Weekday name resolution
    weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    if ds in weekdays:
        target_dow = weekdays.index(ds)
        days_ahead = (target_dow - tomorrow.weekday()) % 7
        target = tomorrow + datetime.timedelta(days=days_ahead)
        return target, None

    # ISO date string
    try:
        target = datetime.date.fromisoformat(date_str.strip())
        return target, None
    except ValueError:
        pass

    return None, f"I don't understand the date '{date_str}'. Try 'tomorrow', a weekday name, or a date like '2025-04-22'."

def get_weather_forecast(location=None, date=None):
    """Fetches a 5-day/3-hour weather forecast from OpenWeather for a specific day.
    Defaults to the device's detected location and tomorrow if no arguments are provided."""
    target_date, err = _resolve_forecast_date(date)
    if err:
        return err

    today = datetime.date.today()
    if target_date <= today:
        return "I can only forecast future dates. For today's current conditions, ask for the current weather."
    if (target_date - today).days > 5:
        return "The forecast is only available up to 5 days ahead. Please ask about a closer date."

    if not location:
        q = DEFAULT_WEATHER_Q
        location_display = DEFAULT_LOCATION_DISPLAY
    else:
        q = location
        location_display = None

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?q={urllib.parse.quote(q)}"
            f"&units=imperial"
            f"&appid={OPENWEATHER_API_KEY}"
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if location_display is None:
            city    = data.get("city", {}).get("name", q)
            country = data.get("city", {}).get("country", "")
            location_display = f"{city}, {country}" if country else city

        # Collect 3-hour slots that fall on the target date (in local time)
        temps      = []
        winds      = []
        conditions = []
        for entry in data.get("list", []):
            slot_dt = datetime.datetime.fromtimestamp(entry["dt"])
            if slot_dt.date() == target_date:
                temps.append(entry["main"]["temp"])
                winds.append(entry["wind"]["speed"])
                conditions.append(entry["weather"][0]["description"])

        date_label = target_date.strftime("%A, %B %d, %Y")

        if not temps:
            return (
                f"No forecast data is available for {date_label} in {location_display}. "
                f"This date may be at the edge of the 5-day forecast window."
            )

        # Aggregate: high/low temp, average wind, most frequent condition
        high = round(max(temps))
        low  = round(min(temps))
        wind = round(sum(winds) / len(winds))
        predominant_condition = max(set(conditions), key=conditions.count)

        return (
            f"The weather forecast for {location_display} on {date_label} is "
            f"{predominant_condition}, with a high of {high} degrees Fahrenheit, "
            f"a low of {low} degrees Fahrenheit, and average winds of {wind} miles per hour."
        )

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Sorry, I couldn't find forecast data for '{location or DEFAULT_LOCATION_DISPLAY}'."
        return "I was unable to retrieve the forecast right now. Please try again in a moment."
    except Exception:
        return "I was unable to retrieve the forecast right now. Please try again in a moment."

def _set_timer(label, duration_seconds):
    """Create (or replace) a named countdown timer."""
    try:
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        return "Invalid duration. Please provide a number of seconds."
    if duration_seconds <= 0:
        return "Duration must be greater than zero."

    with _timers_lock:
        # Cancel existing timer with the same label before replacing
        if label in _timers:
            _timers[label]["timer"].cancel()
            print(f"Timer '{label}' replaced.")

        t = threading.Timer(duration_seconds, _fire_timer, args=[label])
        _timers[label] = {
            "timer": t,
            "start": time.time(),
            "duration": float(duration_seconds),
        }
        t.start()

    if viz is not None and viz.state not in ('countdown', 'visualizing'):
        viz.pre_countdown_state = viz.state
        viz.state = 'countdown'

    # Build a human-readable duration string
    mins, secs = divmod(duration_seconds, 60)
    hrs, mins = divmod(mins, 60)
    parts = []
    if hrs:
        parts.append(f"{hrs} hour{'s' if hrs != 1 else ''}")
    if mins:
        parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
    if secs:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    duration_str = " and ".join(parts) if parts else "0 seconds"

    print(f"Timer '{label}' set for {duration_str}.")
    return f"Timer '{label}' set for {duration_str}."

def _cancel_timer(label):
    """Cancel a running timer by label. If label is omitted and exactly one
    timer is running, cancel that one without asking."""
    with _timers_lock:
        if not label:
            if len(_timers) == 1:
                label = next(iter(_timers))
            elif len(_timers) == 0:
                return "There are no timers currently running."
            else:
                names = ", ".join(f"'{n}'" for n in _timers)
                return f"Multiple timers are running ({names}). Which one should I cancel?"
        entry = _timers.pop(label, None)
    if entry:
        entry["timer"].cancel()
        print(f"Timer '{label}' cancelled.")
        return f"Timer '{label}' cancelled."
    return f"No timer named '{label}' is currently running."

def _get_timer_status(label):
    """Return remaining time for one or all active timers."""
    def _fmt_remaining(entry):
        elapsed = time.time() - entry["start"]
        remaining = max(0.0, entry["duration"] - elapsed)
        mins, secs = divmod(int(remaining), 60)
        hrs, mins = divmod(mins, 60)
        parts = []
        if hrs:
            parts.append(f"{hrs} hour{'s' if hrs != 1 else ''}")
        if mins:
            parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        if secs or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        return " and ".join(parts)

    with _timers_lock:
        snapshot = dict(_timers)

    if label:
        if label not in snapshot:
            return f"No timer named '{label}' is currently running."
        return f"{_fmt_remaining(snapshot[label])} remaining on the '{label}' timer."

    if not snapshot:
        return "No timers are currently running."
    lines = [f"'{lbl}': {_fmt_remaining(entry)} remaining"
             for lbl, entry in snapshot.items()]
    return "Active timers — " + "; ".join(lines) + "."

def _get_ip_location():
    """Fetch city/region from the device's public IP via ip-api.com.
    Returns (q_string, display_string) on success, or None on failure."""
    try:
        url = "http://ip-api.com/json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "success":
            city         = data.get("city", "")
            region       = data.get("regionName", "")
            country_code = data.get("countryCode", "")
            country      = data.get("country", "")
            if city:
                q       = f"{city},{country_code}" if country_code else city
                display = ", ".join(p for p in [city, region, country] if p)
                return q, display
    except Exception as e:
        print(f"IP geolocation error: {e}")
    return None

def save_generated_image(pil_image, prompt_label="image"):
    """Saves a PIL Image to disk. Returns the filename on success or error string."""
    if pil_image is None:
        return "No image to save."

    os.makedirs(SAVE_PATH, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    sanitized_label = prompt_label.replace(" ", "_")[:50]
    output_filename = os.path.join(SAVE_PATH, f"{sanitized_label}_{timestamp}.png")

    try:
        pil_image.save(output_filename, format="PNG")
        print(f"Image saved as {output_filename}")
        return output_filename
    except Exception as e:
        error_msg = f"Failed to save image: {str(e)}"
        print(error_msg)
        return error_msg

def list_saved_images():
    """Returns a list of saved image subjects extracted from filenames."""
    if not os.path.isdir(SAVE_PATH):
        return []

    png_files = [f for f in os.listdir(SAVE_PATH) if f.lower().endswith(".png")]
    if not png_files:
        return []

    subjects = []
    for fname in png_files:
        base = fname[:-4]  # remove .png
        # Timestamp suffix is _MM-DD-YYYY_HH-MM-SS (20 chars including leading _)
        if len(base) > 20 and base[-20] == '_':
            label_part = base[:-20]
        else:
            label_part = base
        subject = label_part.replace("_", " ").strip()
        if subject:
            subjects.append(subject)

    return subjects

def find_saved_image(description):
    """Searches saved images by fuzzy-matching description against filenames.
    Returns (filepath, label, score) for best match, or (None, None, 0)."""
    if not os.path.isdir(SAVE_PATH):
        return None, None, 0

    png_files = [f for f in os.listdir(SAVE_PATH) if f.lower().endswith(".png")]
    if not png_files:
        return None, None, 0

    desc_lower = description.lower().strip()
    desc_words = set(desc_lower.split())

    best_path = None
    best_label = None
    best_score = 0

    for fname in png_files:
        base = fname[:-4]  # remove .png
        # Timestamp suffix is _MM-DD-YYYY_HH-MM-SS (20 chars including leading _)
        if len(base) > 20 and base[-20] == '_':
            label_part = base[:-20]
        else:
            label_part = base

        label_readable = label_part.replace("_", " ").lower().strip()
        label_words = set(label_readable.split())

        seq_ratio = difflib.SequenceMatcher(None, desc_lower, label_readable).ratio()

        if desc_words:
            word_overlap = len(desc_words & label_words) / len(desc_words)
        else:
            word_overlap = 0

        combined = 0.5 * seq_ratio + 0.5 * word_overlap
        if combined > best_score:
            best_score = combined
            best_path = os.path.join(SAVE_PATH, fname)
            best_label = label_part.replace("_", " ")

    THRESHOLD = 0.35
    if best_score >= THRESHOLD:
        return best_path, best_label, best_score
    return None, None, 0

def _reapply_touch_transform():
    """Re-apply touch coordinate transform lost on display wake.
    Mirrors dtoverlay=WS_xinchDSI_Touch,invertedy,swappedxy from config.txt.
    Combined matrix for swappedxy+invertedy: 0 1 0 -1 0 1 0 0 1"""
    try:
        env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0"))
        out = subprocess.check_output(
            ["xinput", "list", "--name-only"],
            text=True, stderr=subprocess.DEVNULL, env=env
        )
        for name in out.splitlines():
            name = name.strip()
            if "touch" in name.lower():
                subprocess.run(
                    ["xinput", "set-prop", name,
                     "Coordinate Transformation Matrix",
                     "0", "1", "0", "-1", "0", "1", "0", "0", "1"],
                    env=env, capture_output=True
                )
                break
    except Exception:
        pass


def wake_screen():
    if _bl_path:
        try:
            max_path = _bl_path.replace("brightness", "max_brightness")
            with open(max_path) as f:
                max_val = f.read().strip()
            with open(_bl_path, "w") as f:
                f.write(max_val)
            _reapply_touch_transform()
            return
        except OSError:
            pass

    if os.system("wlr-randr --output DSI-1 --on 2>/dev/null") != 0:
        os.system("vcgencmd display_power 1 1")
    _reapply_touch_transform()

# --------------------------------------------------------------------------------
# Visualizer Class
# --------------------------------------------------------------------------------

# Module-level reference to the Visualizer singleton, used by _fire_timer.
viz = None

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
        # xset DPMS not supported on Raspberry Pi Bookworm KMS/DRM stack;
        # display power is managed via vcgencmd in blank_screen()/wake_screen().
        pygame.display.set_caption("Lumina")

        global aspect_ratio
        aspect_ratio = get_best_aspect_ratio(self.WIDTH, self.HEIGHT)

        self.BACKGROUND = (0, 0, 0)
        self.WAVEFORM_COLOR = (0, 255, 158)
        self.TEXT_COLOR = (173, 216, 230)  # Light blue (#ADD8E6)

        self.font = pygame.font.Font(None, 74)
        self.text_font = pygame.font.SysFont("Arial Black", 36)
        self.countdown_font = pygame.font.SysFont("Arial Black", 120)
        self.countdown_label_font = pygame.font.SysFont("Arial Black", 48)

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

        # Countdown state: remembers the state to restore when the last timer ends
        self.pre_countdown_state = 'logo'

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

    def display_countdown(self):
        """Render all active timers as label + MM:SS (or HH:MM:SS), stacked vertically."""
        self.screen.fill(self.BACKGROUND)
        with _timers_lock:
            snapshot = list(_timers.items())
        if not snapshot:
            return
        now = time.time()
        rows = []
        for label, entry in snapshot:
            remaining = max(0, int(entry["duration"] - (now - entry["start"])))
            hrs, rem = divmod(remaining, 3600)
            mins, secs = divmod(rem, 60)
            time_str = f"{hrs:d}:{mins:02d}:{secs:02d}" if hrs else f"{mins:02d}:{secs:02d}"
            rows.append((label, time_str))

        row_height = 200
        total_height = len(rows) * row_height
        start_y = self.HEIGHT // 2 - total_height // 2 + row_height // 2
        for i, (label, time_str) in enumerate(rows):
            cy = start_y + i * row_height
            label_surf = self.countdown_label_font.render(label, True, self.TEXT_COLOR)
            time_surf = self.countdown_font.render(time_str, True, self.WAVEFORM_COLOR)
            self.screen.blit(label_surf, label_surf.get_rect(center=(self.WIDTH // 2, cy - 50)))
            self.screen.blit(time_surf, time_surf.get_rect(center=(self.WIDTH // 2, cy + 40)))

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
            elif self.state == 'countdown':
                with _timers_lock:
                    any_timers = bool(_timers)
                if not any_timers:
                    self.state = self.pre_countdown_state or 'logo'
                    continue
                self.display_countdown()
                pygame.display.flip()
                clock.tick(4)
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
    def __init__(self, p_instance, visualizer_instance, porcupine):
        self.audio_buffer = bytearray()
        self.mic_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.p = p_instance
        self.visualizer = visualizer_instance

        # Two-mode mic architecture
        self.porcupine = porcupine
        self.mode = 'active'           # 'guarded' or 'active'
        self.mode_lock = threading.Lock()

        # Frame accumulation buffer for guarded mode
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
            # Transitioning to guarded: clear accumulation buffer
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
        """Resample 24kHz mic audio to 16kHz, then feed to Porcupine
        for wake-word detection."""
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
        self._porcupine_buf = np.concatenate([self._porcupine_buf, samples_16k])

        # Drain Porcupine-sized frames from the buffer
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
    def __init__(self, api_key, ws_url, p_instance, visualizer_instance, porcupine):
        self.sock = Socket(api_key, ws_url)
        self.audio = AudioIO(p_instance, visualizer_instance, porcupine)
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
        self.show_logo_requested = False

    def start(self):
        global _active_session
        self.sock.on_msg = self.on_msg
        self.sock.connect()
        self.audio.on_wake_word = self._handle_wake_word_interrupt
        self.audio.on_exit_word = self._handle_exit_word
        self.audio.set_mode('active')  # User just said "Lumina", expect speech
        self.audio.start_streams()
        threading.Thread(target=self.audio.send_mic, args=(self.sock,), daemon=True).start()
        with _active_session_lock:
            _active_session = self

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
                                "Gets the current weather conditions for a location using the OpenWeather API. "
                                "Use this for present conditions only — use get_weather_forecast for future days. "
                                "If the user did not mention a specific location, call this tool immediately "
                                "with location=null — do NOT ask the user to confirm or name a location first."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "The city or location name to get weather for. "
                                            f"Pass null to automatically use the default ({DEFAULT_LOCATION_DISPLAY}) "
                                            "without asking the user for confirmation."
                                        )
                                    }
                                },
                                "required": ["location"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "get_weather_forecast",
                            "description": (
                                "Returns a weather forecast for a specific future day "
                                "using the OpenWeather API. Supports up to 5 days ahead. "
                                "Use this for any question about tomorrow's weather or a future day. "
                                "If the user did not mention a specific location, call this tool immediately "
                                "with location=null — do NOT ask the user to confirm or name a location first."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "The city or location name to get the forecast for. "
                                            f"Pass null to automatically use the default ({DEFAULT_LOCATION_DISPLAY}) "
                                            "without asking the user for confirmation."
                                        )
                                    },
                                    "date": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "The day to forecast. Accepts: 'tomorrow', a weekday name "
                                            "('Monday'…'Sunday'), or an ISO date string 'YYYY-MM-DD'. "
                                            "Pass null to default to tomorrow."
                                        )
                                    }
                                },
                                "required": ["location", "date"],
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
                                "Turns off the display immediately. "
                                "Call this when the user asks to turn off the screen, blank the display, "
                                "or shut off the monitor. The screen will go dark right away "
                                "but your voice will still be audible."
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
                            "name": "recall_image",
                            "description": (
                                "Searches for a previously saved image by matching the user's "
                                "description against saved image filenames. Call this ONLY when "
                                "the user asks to find, recall, or look up a previously saved "
                                "picture, image, or painting — for example 'find the picture of "
                                "the sunset' or 'recall the painting of a cat'. "
                                "Do NOT use this tool for screen control requests like turning "
                                "the display on or off. Pass the key descriptive words from "
                                "the user's request as the description."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "description": {
                                        "type": "string",
                                        "description": (
                                            "The descriptive terms to search for. Extract the subject "
                                            "from the user's request (e.g., if user says 'show me the "
                                            "painting of a cat', pass 'cat' or 'painting of a cat')."
                                        )
                                    }
                                },
                                "required": ["description"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "set_always_on",
                            "description": (
                                "Enables or disables the always-on display mode. "
                                "When enabled, the screen stays on from 8 AM to 9 PM. "
                                "When disabled, the screen follows the normal inactivity timeout. "
                                "Call this when the user asks to turn always-on mode on or off, "
                                "enable or disable the always-on display, or keep the screen on all day."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "enabled": {
                                        "type": "boolean",
                                        "description": (
                                            "Set to true to enable always-on mode, "
                                            "false to disable it."
                                        )
                                    }
                                },
                                "required": ["enabled"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "list_saved_images",
                            "description": (
                                "Returns a list of subjects from previously saved images. "
                                "Call this when the user asks what images have been saved, "
                                "what pictures are available, or wants to know about their "
                                "saved image collection."
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
                            "name": "show_logo",
                            "description": (
                                "Displays the Lumina logo on the screen. "
                                "Call this when the user asks to show the logo, "
                                "display the start screen, show the home screen, "
                                "or go back to the default display."
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
                            "name": "set_timer",
                            "description": (
                                "Sets a named countdown timer. If a timer with the same label is "
                                "already running it is cancelled and replaced with the new one."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": (
                                            "A short name for the timer, e.g. 'pasta', 'sauce', or 'timer'. "
                                            "Used to identify it when querying or cancelling."
                                        )
                                    },
                                    "duration_seconds": {
                                        "type": "integer",
                                        "description": "How many seconds to count down."
                                    }
                                },
                                "required": ["label", "duration_seconds"],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "cancel_timer",
                            "description": (
                                "Cancels a running timer. If exactly one timer is active, "
                                "call this with no label to cancel it without asking. "
                                "Only ask the user which timer to cancel when two or more are active."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "The label of the timer to cancel. Omit to auto-cancel when only one timer is running."
                                    }
                                },
                                "required": [],
                                "additionalProperties": False
                            }
                        },
                        {
                            "type": "function",
                            "name": "get_timer_status",
                            "description": (
                                "Returns the time remaining on a specific timer or on all active timers."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "label": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "The label of the timer to check, or null to return "
                                            "the status of all active timers."
                                        )
                                    }
                                },
                                "required": ["label"],
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
            threading.Thread(target=_set_alsa_capture, args=(30,), daemon=True).start()

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
                threading.Thread(target=_set_alsa_capture, args=(38,), daemon=True).start()
            elif status == "cancelled":
                # Response was cancelled (by wake word interrupt)
                # Stay in active mode - user is about to speak
                self.ai_responding = False
                threading.Thread(target=_set_alsa_capture, args=(38,), daemon=True).start()
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

            elif func_name == "get_weather_forecast":
                output = get_weather_forecast(args.get("location"), args.get("date"))

            elif func_name == "set_timer":
                output = _set_timer(args.get("label", "timer"), args.get("duration_seconds"))

            elif func_name == "cancel_timer":
                output = _cancel_timer(args.get("label"))

            elif func_name == "get_timer_status":
                output = _get_timer_status(args.get("label"))

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
                self.screen_off_requested = False
                wake_screen()
                if self.visualizer.last_image_surface is not None:
                    self.visualizer.current_image_surface = self.visualizer.last_image_surface
                    self.visualizer.state = 'image'
                    output = "The display is now showing the most recent image."
                else:
                    self.visualizer.state = 'logo'
                    output = "The display is now on. No image has been generated yet, so the logo is shown."

            elif func_name == "turn_off_display":
                self.screen_off_requested = True
                self.screen_on_requested = False
                self.visualizer.state = 'blanked'
                time.sleep(0.1)
                blank_screen()
                output = (
                    "The display has been turned off. "
                    "Confirm to the user that the screen is now off."
                )

            elif func_name == "recall_image":
                description = args.get("description", "")
                if not description:
                    output = "No description provided. Ask the user what image they are looking for."
                else:
                    self.visualizer.set_text("Searching saved images...", description)
                    filepath, label, score = find_saved_image(description)
                    if filepath and os.path.isfile(filepath):
                        try:
                            pil_image = Image.open(filepath)
                            self.visualizer.set_image(pil_image, label)
                            self.new_image_this_session = True
                            output = (
                                f"Found a saved image matching '{description}': "
                                f"'{label}' (confidence: {score:.0%}). "
                                "The image is now displayed on the screen."
                            )
                        except Exception as e:
                            output = f"Found a matching file but failed to open it: {e}"
                    else:
                        output = (
                            f"No saved image was found matching '{description}'. "
                            "Let the user know and suggest they try different descriptive words."
                        )

            elif func_name == "set_always_on":
                enabled = args.get("enabled", True)
                output = set_always_on(enabled)

            elif func_name == "list_saved_images":
                subjects = list_saved_images()
                if subjects:
                    sample_size = min(random.randint(3, 4), len(subjects))
                    sample = random.sample(subjects, sample_size)
                    sample_list = ", ".join(sample)
                    output = (
                        f"There are {len(subjects)} saved images in total. "
                        f"Here are a few: {sample_list}. "
                        "Describe these naturally to the user and ask if they "
                        "would like to hear more."
                    )
                else:
                    output = "There are no saved images yet."

            elif func_name == "show_logo":
                self.screen_on_requested = True
                self.screen_off_requested = False
                self.show_logo_requested = True
                wake_screen()
                self.visualizer.state = 'logo'
                output = "The Lumina logo is now displayed on the screen."

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
        global _active_session
        self._stop_event.set()
        self.audio.stop_streams()
        self.sock.close()
        with _active_session_lock:
            if _active_session is self:
                _active_session = None
        print("Realtime session stopped.")
        print("\nListening for wake word...")

def _app_logic(visualizer):
    """Audio/wake-word loop — runs in a background thread so the pygame
    rendering loop can execute on the main thread (required by SDL2/OpenGL ES
    on Raspberry Pi Bookworm's KMS/DRM stack)."""
    global viz
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-1.5"
    porcupine, pa = None, None
    audio_stream = None

    try:
        # Initialize Porcupine (Wake Word)
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keywords=['Hey-Lumina', 'exit-the-program'],
            sensitivities=[0.3, 0.3]
        )

        pa = pyaudio.PyAudio()

        global _pa_instance
        _pa_instance = pa

        # Optionally resolve the default weather location from the device's public IP.
        if USE_IP_LOCATION:
            global DEFAULT_WEATHER_Q, DEFAULT_LOCATION_DISPLAY
            result = _get_ip_location()
            if result:
                DEFAULT_WEATHER_Q, DEFAULT_LOCATION_DISPLAY = result
                print(f"IP geolocation: default location set to '{DEFAULT_LOCATION_DISPLAY}'.")
            else:
                print("IP geolocation failed — keeping hardcoded default location.")

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
        user_override_off = False

        while True:
            try:

                # --- Always-on display / screen-blanking logic ---
                in_always_on = is_always_on_hours()

                if in_always_on and not user_override_off:
                    # During always-on hours: keep screen on
                    if screen_blanked:
                        wake_screen()
                        screen_blanked = False
                        if visualizer.last_image_surface is not None:
                            visualizer.current_image_surface = visualizer.last_image_surface
                            visualizer.state = 'image'
                        else:
                            visualizer.state = 'logo'
                        print("Screen woken by always-on schedule.")
                    last_interaction_time = time.time()  # prevent timeout
                elif not in_always_on:
                    # Outside always-on hours: normal timeout behavior
                    user_override_off = False  # reset override for next cycle
                    if not screen_blanked and time.time() - last_interaction_time > SCREEN_BLANK_TIMEOUT:
                        visualizer.state = 'blanked'
                        time.sleep(0.05)
                        blank_screen()
                        screen_blanked = True
                        print("Screen blanked due to inactivity.")
                else:
                    # in_always_on and user_override_off: respect user's wish
                    if not screen_blanked and time.time() - last_interaction_time > SCREEN_BLANK_TIMEOUT:
                        visualizer.state = 'blanked'
                        time.sleep(0.05)
                        blank_screen()
                        screen_blanked = True
                        print("Screen blanked (user override during always-on hours).")

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

                    # Start the Realtime Session with Porcupine
                    rt_session = Realtime(OPENAI_API_KEY, url, pa, visualizer, porcupine)

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
                        show_logo = rt_session.show_logo_requested

                        rt_session.stop()

                        # --- Post-session screen behavior (priority order) ---
                        if screen_off:
                            # User asked to turn off the display
                            print("Screen off requested. Blanking screen.")
                            visualizer.state = 'blanked'
                            time.sleep(0.05)
                            blank_screen()
                            screen_blanked = True
                            user_override_off = True
                        elif new_image or screen_on:
                            user_override_off = False
                            print("Showing image/logo, restarting blank timer.")
                            wake_screen()
                            if show_logo or visualizer.last_image_surface is None:
                                visualizer.state = 'logo'
                            else:
                                visualizer.current_image_surface = visualizer.last_image_surface
                                visualizer.state = 'image'
                            last_interaction_time = time.time()
                        elif was_blanked_at_wake:
                            # Woke from blank, no new image or screen commands
                            print("Was blanked at wake with no new image. Re-blanking.")
                            visualizer.state = 'blanked'
                            time.sleep(0.05)
                            blank_screen()
                            screen_blanked = True
                        else:
                            # Default: screen was on, no special commands
                            if visualizer.last_image_surface is not None:
                                visualizer.current_image_surface = visualizer.last_image_surface
                                visualizer.state = 'image'
                            else:
                                visualizer.state = 'logo'
                            last_interaction_time = time.time()

                        # If any timers are active, show the countdown (unless screen is blanked)
                        with _timers_lock:
                            timers_active = bool(_timers)
                        if timers_active and visualizer.state != 'blanked':
                            visualizer.pre_countdown_state = visualizer.state
                            visualizer.state = 'countdown'

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
        if porcupine is not None:
            porcupine.delete()
        visualizer.stop()
        print("App logic cleanup complete.")


def main():
    global viz

    # --- Set ALSA Mixer Levels ---
    # Run 'amixer scontrols' to verify control names for your speakerphone.
    playback_ok = _set_alsa_playback(80)
    capture_ok = _set_alsa_capture(35)
    print(f"ALSA playback (PCM 80%): {'OK' if playback_ok else 'FAILED'}")
    print(f"ALSA capture  (Mic 35%): {'OK' if capture_ok else 'FAILED'}")

    visualizer = Visualizer()
    viz = visualizer

    # _app_logic must run in a background thread so that visualizer.run()
    # (pygame rendering) executes on the main thread — required by SDL2/OpenGL ES
    # on Raspberry Pi Bookworm's KMS/DRM stack, which does not allow GL context
    # sharing across threads.
    app_thread = threading.Thread(target=_app_logic, args=(visualizer,), daemon=True)
    app_thread.start()
    time.sleep(0.5)

    try:
        visualizer.run()   # blocks on main thread until visualizer.stop() is called
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting.")
        visualizer.stop()


if __name__ == "__main__":
    main()
