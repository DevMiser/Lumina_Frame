# Lumina Frame
### AI Voice Assistant & Art Generator for Raspberry Pi 4

Lumina Frame is a voice-activated AI assistant with an integrated AI art generator, running on a Raspberry Pi 4 with an attached DSI touchscreen display and USB speakerphone. Say the wake word **"Lumina"** to start a conversation. Ask questions, request the time or weather, and ask Lumina to generate and display AI artwork — all by voice.

Lumina Frame uses PicoVoice Porcupine for wake-word detection, the OpenAI Realtime API for conversational voice AI, and the Google Gemini API for AI image generation.

A brief demo video of Lumina Frame is here: *(add your link)*

---

## How to Run Lumina Frame on a Raspberry Pi 4

The following steps are required:

- Obtain the necessary hardware — listed below
- Create an OpenAI account and obtain your personal secret API key
- Create a PicoVoice account and obtain your personal secret access key
- Create a Google account and obtain your personal Gemini API key
- Follow the steps below to prepare your Raspberry Pi 4 and install the software

---

## Hardware Requirements

**Raspberry Pi 4** — A Raspberry Pi 4 is required. The 4 GB RAM model is recommended. Earlier Raspberry Pis and the Raspberry Pi 5 are not supported.

**5V Power Supply** — Use the official Raspberry Pi USB-C power supply or equivalent.

**Waveshare 8-inch DSI LCD Display** — This is the display Lumina Frame is designed for. It connects directly to the Raspberry Pi 4 via the DSI ribbon cable connector.
https://www.waveshare.com/8inch-DSI-LCD-C.htm

**USB Speakerphone** — A USB speakerphone provides both microphone input and speaker output in a single device. Any USB speakerphone should work. Lumina Frame is configured to use card index 1 for audio — verify yours matches using `aplay -l` and `arecord -l` after connecting it.

> **Important:** Plug the USB speakerphone into one of the **black USB 2.0 ports** (closest to the sides of the board), not the blue USB 3.0 ports (in the middle). The USB 3.0 controller on the Pi (VL805) generates more RF noise, which can interfere with the speakerphone's mic circuitry, and can occasionally introduce timing differences during enumeration that prevent the speakerphone from being assigned the correct sound card index.

**MicroSD Card** — A 32 GB or larger Class 10 card is recommended.

---

## Create an OpenAI Account and Obtain Your API Key

Open a web browser and navigate to https://openai.com/.

Click on **API** in the upper right-hand corner, then sign up for an account and follow the prompts.

Once logged in, click on your account icon in the upper right-hand corner and select **API keys**, then click **+ Create new secret key**. Copy your API key and keep it in a secure location. You will need it in a later step.

> **Note:** The OpenAI Realtime API requires a paid account with billing enabled. Ensure your account has sufficient credits before running Lumina Frame.

---

## Create a PicoVoice Account and Obtain Your Access Key

Open a web browser and navigate to https://picovoice.ai/.

Click **Start Free** in the upper right-hand corner and follow the prompts to create your account.

After signing up, you will be redirected to a page showing your **AccessKey**. Copy it and keep it in a secure location. You will need it in a later step.

> **Note:** The free PicoVoice tier has usage limits. Lumina Frame uses Porcupine for wake word detection, which draws from your access key's quota.

---

## Create a Google Account and Obtain Your Gemini API Key

Open a web browser and navigate to https://aistudio.google.com/.

Sign in with your Google account and click **Get API key**, then click **Create API key**. Copy your API key and keep it in a secure location. You will need it in a later step.

> **Note:** A free Gemini API tier is available, though it has rate limits. Image generation requires a model that supports it — Lumina Frame uses `gemini-3.1-flash-image-preview`. Check https://ai.google.dev/ for current model availability.

---

## Prepare Your Raspberry Pi 4

These instructions assume you already have a Raspberry Pi 4 set up and running **Raspberry Pi OS (64-bit, Bookworm)**. If not, use the Raspberry Pi Imager to install it. Be sure to use the **64-bit** version — the 32-bit version may produce memory errors.

### 1. Update Your System

Open a terminal and enter the following commands in order:

```
sudo apt update
sudo apt full-upgrade
```

If asked whether you want to continue, enter **Y** and press Enter. When the upgrade completes, reboot:

```
sudo reboot
```

Log back in after the reboot.

### 2. Install System-Level Dependencies

Some packages must be installed at the system level via `apt` before setting up the Python environment. Open a terminal and enter the following commands in order:

```
sudo apt install portaudio19-dev
sudo apt install x11-xserver-utils
sudo apt-get install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
```

If asked whether you want to continue, enter **Y** and press Enter.

### 3. Clone the Lumina Frame Repository

Open a terminal and enter the following commands:

```
cd /home/pi
git clone https://github.com/DevMiser/Lumina_Frame.git
cd Lumina_Frame
```

> If your clone creates a differently named folder, rename it or adjust the paths in the next steps accordingly. Lumina Frame expects its files to be located at `/home/pi/Lumina/`.

Move or copy the files into place:

```
mkdir -p /home/pi/Lumina
cp -r /home/pi/Lumina_Frame/* /home/pi/Lumina/
cd /home/pi/Lumina
```

### 4. Create a Python Virtual Environment

Because Raspberry Pi OS Bookworm enforces PEP 668, all Python packages must be installed inside a virtual environment rather than system-wide. Create and activate a virtual environment by entering the following commands:

```
python -m venv venv
source venv/bin/activate
```

Your terminal prompt will change to show `(venv)` at the beginning, confirming the virtual environment is active.

### 5. Install Python Dependencies

With the virtual environment active, install all required packages:

```
pip install -r requirements.txt
```

This may take several minutes on a Raspberry Pi 4.

### 6. Create Your .env File with Your API Keys

Lumina Frame loads its API keys from a `.env` file located in the same folder as `Lumina_Frame.py`. Create this file by entering the following commands:

```
cd /home/pi/Lumina
nano .env
```

Add the following three lines to the file, replacing the placeholder text with your actual keys:

```
OPENAI_API_KEY=your_openai_api_key_here
PICOVOICE_ACCESS_KEY=your_picovoice_access_key_here
GOOGLE_API_KEY=your_google_api_key_here
```

Press **Ctrl + X**, then **Y**, then **Enter** to save the file.

> **Important:** Never share your `.env` file or commit it to a public repository. The `.gitignore` file included with this project is already configured to exclude it.

### 7. Verify the Logo File Is in Place

Lumina Frame displays a logo on startup. Confirm the logo file is present at the expected location:

```
ls /home/pi/Lumina/Lumina_Frame_Logo.png
```

If the file is missing, copy or move it to that path.

### 8. Pin Your Speakerphone to ALSA Card Index 1

Lumina Frame is configured to use ALSA card index **1** for the USB speakerphone. To ensure your speakerphone is always assigned to card 1 — regardless of the order devices are detected at boot — you need to pin it in the ALSA module configuration.

Open a terminal and enter:

```
sudo nano /etc/modprobe.d/alsa-base.conf
```

If you are using the same USB speakerphone as the one used in this project, paste the following lines into the file:

```
options snd_bcm2835 index=-2
options snd-usb-audio index=1 vid=0xf201 pid=0x3220
```

Press **Ctrl + X**, then **Y**, then **Enter** to save, then reboot:

```
sudo reboot
```

After rebooting, open a terminal and enter:

```
aplay -l
```

You should see your USB speakerphone listed at **card 1**, similar to:

```
card 1: USB [USB Audio Device], device 0: ...
```

**If you are using a different speakerphone**, you will need to find its Vendor ID and Product ID first. Enter the following command:

```
lsusb
```

You will see output similar to:

```
Bus 001 Device 004: ID 1234:5678 Acme USB Speakerphone
```

The portion after **ID** contains your Vendor ID and Product ID separated by a colon — `1234` and `5678` in the example above (your numbers will be different). Then redo the steps above, substituting your actual Vendor ID and Product ID:

```
options snd_bcm2835 index=-2
options snd-usb-audio index=1 vid=0x1234 pid=0x5678
```

This ensures Lumina Frame can reliably adjust the microphone gain via ALSA Mixer each time the program starts.

---

## Run the Program

Make sure your Waveshare DSI display is connected and your USB speakerphone is plugged in. Then open a terminal, navigate to the Lumina folder, activate the virtual environment, and run the program:

```
cd /home/pi/Lumina
source venv/bin/activate
python Lumina_Frame.py
```

Wait for the Lumina logo to appear on the DSI display.

---

## Using Lumina Frame

### Waking Lumina

Say the wake word:

> **"Lumina"**

When Lumina detects its wake word, Lumina will begin listening. The display will show a waveform that animates in sync with Lumina's voice as it responds.

### Talking to Lumina

Once awake, speak naturally. Lumina will respond conversationally. For example:

*What time is it?*

*What's the weather like today?*

*What is the capital of Australia?*

### Generating Images

Ask Lumina to create AI-generated artwork using natural language. For example:

*Draw a lighthouse on a rocky coast at sunset.*

*Paint a portrait of a fox in the style of Van Gogh.*

*Generate a schematic of a time machine.*

*Create an image of a bustling Japanese street market at night.*

Lumina will acknowledge your request, generate the image using Google Gemini, and display it on the DSI screen.

### Saving Images

To save the most recently generated image to `/home/pi/Lumina/Saved_Images/`, say:

*Save the image.*

Lumina will confirm the filename after saving.

### Controlling the Display

To show the most recently generated image (or the logo if none has been generated):

*Show the image.*

To blank the display:

*Turn off the screen.*

The display will also blank automatically after **10 minutes** of wake-word inactivity.

### Exiting the Program

To exit Lumina Frame, say:

> **"Exit the program"**

Lumina Frame will shut down cleanly.

You can also press **Ctrl + C** in the terminal.

---

## Running Lumina Frame Automatically at Startup (Optional)

After everything is working, you may want Lumina Frame to launch automatically when the Raspberry Pi boots. To do so, create a systemd service file:

```
sudo nano /etc/systemd/system/lumina.service
```

Add the following content:

```
[Unit]
Description=Lumina Frame
After=graphical.target

[Service]
User=pi
WorkingDirectory=/home/pi/Lumina
Environment=DISPLAY=:0
ExecStart=/home/pi/Lumina/venv/bin/python /home/pi/Lumina/Lumina_Frame.py
Restart=on-failure

[Install]
WantedBy=graphical.target
```

Press **Ctrl + X**, then **Y**, then **Enter** to save. Then enable and start the service:

```
sudo systemctl daemon-reload
sudo systemctl enable lumina.service
sudo systemctl start lumina.service
```

Lumina Frame will now start automatically each time the Raspberry Pi boots.

---

## Configuration Reference

The following constants near the top of `Lumina_Frame.py` can be adjusted to suit your setup:

| Constant | Default | Description |
|---|---|---|
| `INACTIVITY_TIMEOUT` | `3` seconds | How long Lumina waits after silence before ending a session |
| `SCREEN_BLANK_TIMEOUT` | `600` seconds | How long before the display blanks due to inactivity |
| `LOGO_PATH` | `/home/pi/Lumina/Lumina_Frame_Logo.png` | Path to the startup logo image |
| `SAVE_PATH` | `/home/pi/Lumina/Saved_Images` | Directory where generated images are saved |

The default weather location is **Delray Beach, Florida**. To change it, update the `lat`, `lon`, and `location_display` values in the `get_current_weather()` function.

---

## Project Structure

```
Lumina/
├── Lumina_Frame.py          # Main program
├── requirements.txt         # Python dependencies
├── .env                     # Your API keys (never commit this)
├── .env.example             # Template showing required keys
├── .gitignore
├── README.md
├── Lumina_Frame_Logo.png    # Startup logo displayed on DSI screen
└── Saved_Images/            # Generated images saved here
```

---

## Troubleshooting

**The display shows nothing on startup.**
Confirm the DSI ribbon cable is fully seated at both ends. Verify the display is enabled in `raspi-config` under Interface Options > Display.

**Lumina does not respond to its wake word.**
Check that your USB speakerphone is recognized at card index 1 using `arecord -l`. Confirm your PicoVoice access key is correctly entered in `.env`.

**Image generation fails.**
Verify your Google API key is valid and that you have access to the `gemini-3.1-flash-image-preview` model. Check your quota at https://aistudio.google.com/.

**The virtual environment is not found on startup.**
If running as a service, confirm the `ExecStart` path in the systemd service file points to `/home/pi/Lumina/venv/bin/python`.

**Speaker audio causes Lumina to interrupt itself.**
The program includes a guarded mic mode that suppresses speaker bleed during AI speech. If self-interruption occurs, try increasing the `threshold` value in the `server_vad` section of the session configuration in `Lumina_Frame.py`.

---

*Provided by DevMiser — https://github.com/DevMiser*
