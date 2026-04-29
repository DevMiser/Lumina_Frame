# Lumina Frame
### AI Voice Assistant & Art Generator for Raspberry Pi 4

Lumina Frame is a voice-activated AI assistant with an integrated AI art generator, running on a Raspberry Pi 4 with an attached DSI touchscreen display and USB speakerphone. Say the wake word **"Hey Lumina"** to start a conversation. Ask questions, request the time or weather, generate AI artwork, set countdown timers, recall previously saved images, and more — all by voice.

Lumina Frame uses PicoVoice Porcupine for wake-word detection, the OpenAI Realtime API for conversational voice AI, Google Gemini' Nano Banana 2 for AI image generation, and the OpenWeather API for current weather conditions and multi-day forecasts.

A brief demo video of Lumina Frame is here: *(add your link)*

---

## How to Run Lumina Frame on a Raspberry Pi 4

The following steps are required:

- Obtain the necessary hardware — listed below
- Create an OpenAI account and obtain your personal secret API key
- Create a Google account and obtain your Gemini API key
- Create a PicoVoice account and obtain your personal secret access key (free)
- Create an OpenWeather account and obtain your personal API key (free)
- Follow the steps below to prepare your Raspberry Pi 4 and install the software
- 3D print the frame with integrated speakerphone cradle (optional)

---

## Hardware Requirements

**Raspberry Pi 4** — A [Raspberry Pi 4](https://www.canakit.com/raspberry-pi-4-2gb.html)) is required. 2 GB of RAM model or more is recommended. Earlier Raspberry Pis and the Raspberry Pi 5 are not supported.

**5V Power Supply** — Use the [official Raspberry Pi USB-C power supply](https://www.canakit.com/official-raspberry-pi-4-power-supply-black.html) or equivalent.

**Waveshare 8-inch DSI LCD Display** — This is the display Lumina Frame is designed for. It connects directly to the Raspberry Pi 4 via the DSI ribbon cable connector.
https://www.waveshare.com/8inch-DSI-LCD-C.htm

**USB Speakerphone** — A USB speakerphone provides both microphone input and speaker output in a single device. I used the [RayBit USB Speakerphone](https://www.amazon.com/dp/B0B4JTMQ9H/). Any USB speakerphone with echo noise cancellation should work, although I am cannot say for certain because I have not tested others. Use the RayBit if you want to use the 3D printed frame because it is specifically designed to hold the RayBit.

> **Important:** Plug the USB speakerphone into one of the **black USB 2.0 ports** (closest to the sides of the board), not the blue USB 3.0 ports (in the middle). The USB 3.0 controller on the Pi (VL805) generates more RF noise, which can interfere with the speakerphone's mic circuitry, and can occasionally introduce timing differences during enumeration that prevent the speakerphone from being assigned the correct sound card index.

**MicroSD Card** — A 64 GB or larger card rated **A2** and **V30** (or U3) from a reputable brand is recommended. The A2 rating ensures good random I/O performance for a responsive OS, and V30/U3 provides solid write speed well beyond what the Raspberry Pi 4's SD interface requires. Purchase from a reputable retailer to avoid counterfeit cards. I used a [SanDisk Extreme Pro](https://www.amazon.com/SanDisk-microSDXC-RescuePro-Performance-Smartphones/dp/B09X7BYSFG/).

**Phillips Flat Head Screws (Optional)** - You will need seven [Phillips flat head screws](https://boltdepot.com/Product-Details?product=6854) if you decide to use the optional 3D printed frame. The ones I used are 2.5 x 0.45 x 8mm.

**USB C Male to Female 90 Degree Angle Adapter (Optional)** - If you use the optional 3D printed frame and want the power cord at the bottom, you will need an [angle adapter](https://www.amazon.com/dp/B0B462QMMK?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_11&th=1).

---

## Create an OpenAI Account and Obtain Your API Key

Open a web browser and navigate to https://openai.com/.

Click on the dropdown menu for **Log in** in the upper right-hand corner, then click on **API Platform** and sign up for an account.

Once logged in, click on **Create API key** amd follow the instructions. Copy your API key and keep it in a secure location. You will need it in a later step.

> **Note:** Your OpenAI API key is used for the Realtime conversational API. The OpenAI Realtime API requires a paid account with billing enabled. Ensure your account has sufficient credits before running Lumina Frame.

---

**### Create a Google Account and Obtain Your Gemini API Key**

Open a web browser and navigate to https://aistudio.google.com/.

Scroll down the page and click on **Get an API key**. Sign in with your Google account (or create one), then click **Create API key** and follow the prompts to generate a key. Copy it and keep it in a secure location. You will need it in a later step.

> **Note:** The free Gemini API tier is insufficient for using Nano Banana 2 for image generation. You will need to set up a pay-as-you-go billing account connected to you API key.

---

## Create a PicoVoice Account and Obtain Your Access Key

Open a web browser and navigate to https://picovoice.ai/.

Click **Start Free** in the upper right-hand corner and follow the prompts to create your account.

After signing up, you will be redirected to a page showing your **AccessKey**. Copy it and keep it in a secure location. You will need it in a later step.

> **Note:** The free PicoVoice tier has usage limits. Lumina Frame uses Porcupine for wake word detection, which draws from your access key's quota.  I have not exceeded the free usage limits during normal use of Lumina.

---

## Create an OpenWeather Account and Obtain Your API Key

Open a web browser and navigate to https://openweathermap.org/.

Click **Get API key** and create a free account. Once logged in, click **API keys**. Copy the default key or generate a new one. Copy it and keep it in a secure location. You will need it in a later step.

> **Note:** The free tier of OpenWeather is sufficient for Lumina Frame. It provides free access to the current weather endpoint and the 5-day/3-hour forecast endpoint used for weather queries.

---

## Prepare Your Raspberry Pi 4

These instructions assume you already have a Raspberry Pi 4 set up and running **Raspberry Pi OS (64-bit, Debian Trixie)**. If not, use the Raspberry Pi Imager to install it, which is available here: https://www.raspberrypi.com/software/. Be sure to use the **64-bit** Debian Trixie version — the 32-bit version may produce memory errors.

> **Note:** Raspberry Pi OS Trixie is based on Debian 13 with kernel 6.12 LTS and Python 3.13. The Raspberry Pi Foundation recommends doing a clean install rather than upgrading in place from a previous release such as Bookworm.  The Debian OS also often asks for the Pi's password when asked to take certain actions, including many commands that begin with "sudo".  Whenever asked, type the password for your device and press Enter.

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


### 2. Install the Waveshare Display Driver

The Waveshare 8inch DSI LCD (C) driver is built into the Raspberry Pi OS Trixie kernel — no manual driver installation is required. You simply need to add one line to the Raspberry Pi configuration file to enable it.

Open the configuration file:

```
sudo nano /boot/firmware/config.txt
```

Scroll to the very end of the file and add the following line:

```
dtoverlay=vc4-kms-dsi-waveshare-panel,8_0_inch
```

Press **Ctrl + X**, then **Y**, then **Enter** to save. Then reboot:

```
sudo reboot
```

After rebooting, the Waveshare display should be active. If the display remains blank, confirm the DSI ribbon cable is fully seated at both ends and that the cable's gold contacts are oriented correctly.

> **Note:** If you later run `sudo apt full-upgrade` and the display stops working, re-open `/boot/firmware/config.txt` and verify the `dtoverlay` line is still present. A system upgrade can occasionally overwrite kernel overlay files, and re-saving the config line and rebooting is all that is needed to restore normal operation.

### 3. Reorient the Display Screen (Optional)

If you are going to put the display in the 3D-printed or other frame and want to have the power port on the Raspberry Pi at the bottom of the frame, you will need to reorient the axes of the display screen. To do so, follow the instructions under the heading **Trixie/Bookworm Display Rotation** in the display's [wiki](https://www.waveshare.com/wiki/8inch_DSI_LCD_(C)). 

> **Hint:** after clicking **Apply** on the last step you may need to click the **Ok** button on the touchscreen itself instead of with your mouse if you are connected via Raspberry Pi Connect.

Then reboot:

```
sudo reboot
```

### 4. Disable the Virtual Keyboard - Squeekboard (Optional)

The Trixie OS uses Wayland and the system automatically launches the Squeekboard on screen keyboard whenever a text field is touched. If you prefer to stop the keyboard from popping up, you can disable it.  To do so, open a terminal and enter the following command:

 ```
sudo raspi-config nonint do_squeekboard S3
```

Then reboot:

```
sudo reboot
```

### 5. Install System-Level Dependencies

Some packages must be installed at the system level via `apt` before setting up the Python environment. Open a terminal and enter the following commands in order:

```
sudo apt install portaudio19-dev
sudo apt install x11-xserver-utils
sudo apt-get install libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
sudo apt install pipewire pipewire-alsa wireplumber
```

If asked whether you want to continue, enter **Y** and press Enter.

### 6. Clone the Lumina Frame Repository

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

### 7. Create a Python Virtual Environment

Debian 13 (and therefore Raspberry Pi OS Trixie) ships Python 3.13 and enforces PEP 668, so all Python packages must be installed inside a virtual environment rather than system-wide. Create and activate a virtual environment by entering the following commands:

```
python -m venv venv
source venv/bin/activate
```

Your terminal prompt will change to show `(venv)` at the beginning, confirming the virtual environment is active.

### 8. Install Python Dependencies

With the virtual environment active, install all required packages:

```
pip install -r requirements.txt
```

This may take several minutes on a Raspberry Pi 4.

### 9. Create Your .env File with Your API Keys

Lumina Frame loads its API keys from a `.env` file located in the same folder as `Lumina_Frame9.py`. Create this file by entering the following commands:

```
cd /home/pi/Lumina
nano .env
```

Add the following four lines to the file, replacing the placeholder text with your actual keys:

```
GOOGLE_API_KEY="put your Google API key here between the quotation marks"
OPENAI_API_KEY="put your OpenAI API key here between the quotation marks"
OPENWEATHER_API_KEY="put your OpenWeather API key here between the quotation marks"
PICOVOICE_ACCESS_KEY="put your Picovoice Access key here between the quotation marks"
```

Press **Ctrl + X**, then **Y**, then **Enter** to save the file.

> **Important:** Never share your `.env` file or commit it to a public repository. The `.gitignore` file included with this project is already configured to exclude it.

### 10. Pin Your Speakerphone to ALSA Card Index 1

Lumina Frame is configured to use ALSA card index **1** for the USB speakerphone. To ensure your speakerphone is always assigned to card 1 — regardless of the order devices are detected at boot — you need to pin it in the ALSA module configuration.

Open a terminal and enter:

```
sudo nano /etc/modprobe.d/alsa-base.conf
```

If you are using the RayBit USB speakerphone recommended for this project, paste the following lines into the file:

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

**### 11. Configure PipeWire Audio**

Raspberry Pi OS Trixie uses **PipeWire** as its audio server. PipeWire handles all audio routing — including USB speakerphone access, sample-rate conversion, and sharing the device between multiple applications — so no `~/.asoundrc` file is needed.

First, enable and start the PipeWire services for your user session:

```
systemctl --user enable pipewire pipewire-pulse wireplumber
systemctl --user start pipewire pipewire-pulse wireplumber
```

Verify PipeWire is running:

```
pactl info
```

You should see a line similar to `Server Name: PulseAudio (on PipeWire ...)`. If you see this, PipeWire is active.

Next, create a PipeWire configuration file to increase the audio buffer size. This prevents clicking and stuttering that can occur when the AI voice audio arrives over the network in bursts:

```
mkdir -p ~/.config/pipewire/pipewire.conf.d
sudo nano ~/.config/pipewire/pipewire.conf.d/fix-clicks.conf
```

Paste the following into the file:

```
context.properties = {
    default.clock.rate        = 48000
    default.clock.quantum     = 2048
    default.clock.min-quantum = 1024
    default.clock.max-quantum = 8192
}
```

Press **Ctrl + X**, then **Y**, then **Enter** to save. Then restart PipeWire to apply the change:

```
systemctl --user restart pipewire pipewire-pulse wireplumber
```

> **Note:** Do **not** create a `~/.asoundrc` file. PipeWire manages ALSA routing automatically, and an `~/.asoundrc` file will conflict with it.

### 12. Move the Keyword Files

Move the Lumina keyword files to the Porcupine raspberry-pi keywords folder by opening a terminal and entering the 
following commands: 

```
mv /home/pi/Lumina/Hey-Lumina_en_raspberry-pi_v4_0_0.ppn /home/pi/Lumina/venv/lib/python3.13/site-packages/pvporcupine/resources/keyword_files/raspberry-pi
mv /home/pi/Lumina/exit-the-program_en_raspberry-pi_v4_0_0.ppn /home/pi/Lumina/venv/lib/python3.13/site-packages/pvporcupine/resources/keyword_files/raspberry-pi
```

Important - Note there are two blank spaces in each of the above commands – one between 
"mv" and "/home" and one between ".ppn" and "/home". Be sure to include them. There are no other spaces between the letters. 

---

## Run the Program

Make sure your Waveshare DSI display is connected and your USB speakerphone is plugged in. Then open a terminal, navigate to the Lumina folder, activate the virtual environment, and run the program by entering these commands:

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

> **"Hey Lumina"**

When Lumina detects its wake word, it will begin listening. The display will show an animated orb that pulses in sync with Lumina's voice as it responds. You can also say **"Hey Lumina"** at any time to interrupt Lumina mid-response and ask a new question.

### Talking to Lumina

Once awake, speak naturally. Lumina will respond conversationally. For example:

*What time is it?*

*What's the weather like today?*

*What will the weather be like on Friday?*

*Who won the last Men's World Cup?*

*Explain entropy.*

### Generating Images

Ask Lumina to create AI-generated artwork using natural language. For example:

*Draw an apple orchard at sunset.*

*Paint a cheeseburger in the style of Van Gogh.*

*Generate a schematic of a time machine.*

*Create an image of chipmunks racing go-carts.*

Lumina will acknowledge your request, generate the image using Google Gemini Nano Banana 2, and display it on the display screen. The image orientation (landscape, square, or portrait) is chosen automatically based on your display's resolution.

### Saving Images

To save the most recently generated or edited image to `/home/pi/Lumina/Saved_Images/`, say:

*Save the image.*

Lumina will confirm the filename after saving.

### Recalling Saved Images

To find and display a previously saved image, say:

*Find the picture of the sunset.*

*Show me the painting of a cat.*

*Recall the image of the Japanese street market.*

Lumina will search your saved images by description and display the closest match. If no match is found, Lumina will let you know and suggest trying different words.

### Listing Saved Images

To hear what images have been saved, say:

*What images have you saved?*

*Tell me about the pictures you have.*

Lumina will describe a random sample of saved images and let you know how many are saved in total.

### Setting Timers

Lumina supports multiple named countdown timers. For example:

*Set a ten-minute timer.*

*Set a pasta timer for twelve minutes.*

*How much time is left on the pasta timer?*

*Cancel the pasta timer.*

While a timer is running, the display shows a live countdown. When a timer finishes, Lumina will announce it. If no session is active when the timer fires, a chime will play and the finish message will appear on the display.

### Controlling the Display

To show the most recently generated image (or the logo if none has been generated):

*Show the image.*

*Turn on the screen.*

To return to the Lumina logo:

*Show the logo.*

*Go back to the home screen.*

To blank the display:

*Turn off the screen.*

The display will also blank automatically after **10 minutes** of wake-word inactivity outside of always-on hours.

### Always-On Display Mode

By default, the display stays on automatically between **8:00 AM and 9:00 PM**. You can control this feature by voice:

*Turn on always-on mode.*

*Turn off always-on mode.*

If you manually blank the display during always-on hours (by asking Lumina to turn off the screen), that setting will be respected until the next always-on cycle begins.

### Exiting the Program

To exit Lumina Frame, say:

> **"Exit the program"**

Lumina Frame will shut down cleanly.

You can also press **Ctrl + C** in the terminal.

---

## Running Lumina Frame Automatically at Startup (Optional)

After everything is working, you may want Lumina Frame to launch automatically when the Raspberry Pi boots. On Raspberry Pi OS Trixie, the most reliable way to do this is with an XDG autostart file, which tells the Wayfire desktop session to launch Lumina Frame automatically once the display, audio, and all session services are fully up.

Open a terminal and enter:

```
mkdir -p ~/.config/autostart
nano ~/.config/autostart/lumina.desktop
```

Add the following content:

```
[Desktop Entry]
Type=Application
Name=Lumina Frame
Exec=/bin/bash -c 'cd /home/pi/Lumina && /home/pi/Lumina/venv/bin/python /home/pi/Lumina/Lumina_Frame.py'
X-GNOME-Autostart-enabled=true
```

Press **Ctrl + X**, then **Y**, then **Enter** to save. Lumina Frame will now launch automatically each time the Raspberry Pi boots. The desktop will appear on the display for a few seconds before Lumina Frame launches and the logo appears.

> **Note:** If you ever need to stop Lumina Frame from launching at startup, delete or rename the file: `rm ~/.config/autostart/lumina.desktop`

> **Note:** If the cursor is showing on the display screen after using autostart, gently tap a finger on the touchscreen and the cursor will disappear.

---

## Configuration Reference

The following constants near the top of `Lumina_Frame.py` can be adjusted to suit your setup:

| Constant | Default | Description |
|---|---|---|
| `INACTIVITY_TIMEOUT` | `3` seconds | How long Lumina waits after silence before ending a session |
| `SCREEN_BLANK_TIMEOUT` | `600` seconds | How long before the display blanks due to inactivity |
| `ALWAYS_ON_ENABLED` | `True` | Whether the always-on display schedule is active at startup |
| `ALWAYS_ON_START_HOUR` | `8` | Hour (24h) when always-on mode begins each day |
| `ALWAYS_ON_END_HOUR` | `21` | Hour (24h) when always-on mode ends each day |
| `USE_IP_LOCATION` | `True` | Whether to auto-detect your location via IP for weather queries |
| `DEFAULT_WEATHER_Q` | `"New York,NY,US"` | Fallback weather query location (used if IP geolocation fails) |
| `DEFAULT_LOCATION_DISPLAY` | `"New York, NY"` | Fallback location display name |
| `LOGO_PATH` | `/home/pi/Lumina/Lumina_Frame_Logo.png` | Path to the startup logo image |
| `SAVE_PATH` | `/home/pi/Lumina/Saved_Images` | Directory where generated images are saved |

If `USE_IP_LOCATION` is `True`, Lumina Frame will attempt to determine your location automatically from your device's public IP address at startup. If geolocation fails, it will fall back to the hardcoded `DEFAULT_WEATHER_Q` and `DEFAULT_LOCATION_DISPLAY` values.

---

## Project Structure

```
Lumina/
├── Lumina_Frame.py # Main program
├── requirements.txt         # Python dependencies
├── .env                     # Your API keys (never commit this)
├── .env.example             # Template showing required keys
├── .gitignore
├── README.md
├── Lumina_Frame_Logo.png    # Startup logo displayed on DSI screen
└── Saved_Images/            # Generated images saved here
```

---
## Printing and Assembling the Lumina Frame Enclosure

If you would like to use the optional 3D-printed frame and speakerphone cradle, follow these instructions.

3D print the frame, cradle, cradle bottom, and four of the tabs [Figure 1].  The STLs for these 3D parts are on this GitHub repository. The recommended setting for slicing the STLs are 0.20mm quality with 25% infill. Only the frame and cardles require supports while printing **add detail**

Use four of the Phillips pan head screws to screw the tabs in place to hold the display on the frame [Figure 2]. Insert the speakerphone in the cradle, put on the cradle bottom and hold it in place with other three screws [Figure 3].

Insert the prongs on the speakerphone cradle into the frame [Figure 4]. This is a tight fit and should hold on its own but use superglue if you want to permanently bond them together.

Use the optional angle adapter for the power port.

---

## Troubleshooting

**The display shows nothing on startup.**
Confirm the DSI ribbon cable is fully seated at both ends. Verify the display is enabled in `raspi-config` under Interface Options > Display.

**The screen never blanks, or screen-control voice commands have no effect.**
Trixie uses Wayland by default, which is fully supported. Confirm that the `/sys/class/backlight/10-0045/brightness` sysfs path exists by running `ls /sys/class/backlight/`. If the folder name differs, update the `_backlight_path()` function in `Lumina_Frame.py` with the correct name.

**Lumina does not respond to its wake word.**
Check that your USB speakerphone is recognized at card index 1 using `arecord -l`. Confirm your PicoVoice access key is correctly entered in `.env`.

**Image generation or editing fails.**
Verify your Google Gemina API key is valid and is correctly entered in `.env`and that your account has sufficient credits.

**Weather queries fail or return errors.**
Verify your OpenWeather API key is correctly entered in `.env`. New API keys can take a few minutes to activate after registration. Confirm your network connection is working.

**Speaker audio causes Lumina to interrupt itself.**
The program uses a guarded mic mode that suppresses speaker bleed during AI speech. If self-interruption occurs, try increasing the `threshold` value in the `server_vad` section of the session configuration in `Lumina_Frame.py`.

**Timers fire but Lumina doesn't announce them.**
If no active session is open when a timer expires, the program will play a chime and display the timer name on screen instead. This is expected behavior.

**Audio device errors on startup (`Invalid sample rate` or `Device unavailable`).**
Confirm PipeWire is running: `pactl info` should show `PulseAudio (on PipeWire ...)`. If it is not running, start it with `systemctl --user start pipewire pipewire-pulse wireplumber`. Also confirm there is **no** `~/.asoundrc` file in your home directory (`ls -la ~`). If one exists, delete it with `rm ~/.asoundrc` and restart PipeWire.

**Clicking or stuttering when Lumina speaks.**
Confirm the PipeWire quantum config file exists at `~/.config/pipewire/pipewire.conf.d/fix-clicks.conf` and that the `default.clock.quantum` is set to `2048`. Restart PipeWire after any changes: `systemctl --user restart pipewire pipewire-pulse wireplumber`.

> **Lumina Frame does not launch at startup (if yu have set it to do so).**
> Confirm the autostart file exists: `ls ~/.config/autostart/lumina.desktop`. If it is missing, re-create it following the steps in the autostart section above. To check whether the script is currently running, enter `pgrep -a python` in a terminal.

---

*Provided by DevMiser — https://github.com/DevMiser*
