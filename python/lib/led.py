from __future__ import print_function
from __future__ import division


import platform
import numpy as np
import config as config

# ESP8266 uses WiFi communication
if config.settings["configuration"]["DEVICE"] == 'esp8266':
    import socket
    from subprocess import check_output
    from time import sleep
    _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _sock.settimeout(0.005)
# Raspberry Pi controls the LED strip directly
elif config.settings["configuration"]["DEVICE"] == 'pi':
    import neopixel
    strip = neopixel.Adafruit_NeoPixel(config.settings["configuration"]["N_PIXELS"], config.settings["configuration"]["LED_PIN"],
                                       config.settings["configuration"]["LED_FREQ_HZ"], config.settings["configuration"]["LED_DMA"],
                                       config.settings["configuration"]["LED_INVERT"], config.settings["configuration"]["BRIGHTNESS"])
    strip.begin()

_gamma = np.load(config.settings["configuration"]["GAMMA_TABLE_PATH"])
"""Gamma lookup table used for nonlinear brightness correction"""

_prev_pixels = np.tile(253, (3, config.settings["configuration"]["N_PIXELS"]))
"""Pixel values that were most recently displayed on the LED strip"""

pixels = np.tile(1, (3, config.settings["configuration"]["N_PIXELS"]))
"""Pixel values for the LED strip"""

_is_python_2 = int(platform.python_version_tuple()[0]) == 2

def _update_esp8266():
    """Sends UDP packets to ESP8266 to update LED strip values

    The ESP8266 will receive and decode the packets to determine what values
    to display on the LED strip. The communication protocol supports LED strips
    with a maximum of 256 LEDs.

    The packet encoding scheme is:
        |i|r|g|b|
    where
        i (0 to 255): Index of LED to change (zero-based)
        r (0 to 255): Red value of LED
        g (0 to 255): Green value of LED
        b (0 to 255): Blue value of LED
    """
    global pixels, _prev_pixels
    # Truncate values and cast to integer
    pixels = np.clip(pixels, 0, config.settings["configuration"]["maxBrightness"]).astype(int)
    # Optionally apply gamma correction
    p = _gamma[pixels] if config.settings["configuration"]["SOFTWARE_GAMMA_CORRECTION"] else np.copy(pixels)
    MAX_PIXELS_PER_PACKET = 255
    # Pixel indices
    idx = range(pixels.shape[1])
    #idx = [i for i in idx if not np.array_equal(p[:, i], _prev_pixels[:, i])]
    n_packets = len(idx) // MAX_PIXELS_PER_PACKET + 1
    idx = np.array_split(idx, n_packets)

    m = []
    for i in range(config.settings["configuration"]["N_PIXELS"]):
        #m.append(i)  # Index of pixel to change
        m.append(pixels[0][i])  # Pixel red value
        m.append(pixels[1][i])  # Pixel green value
        m.append(pixels[2][i])  # Pixel blue value
    m = bytes(m)
    _sock.sendto(m, (config.settings["configuration"]["UDP_IP"], config.settings["configuration"]["UDP_PORT"]))
    
    # for packet_indices in idx:
    #     m = '' if _is_python_2 else []
    #     for i in packet_indices:
    #         if _is_python_2:
    #             m += chr(i) + chr(pixels[0][i]) + chr(pixels[1][i]) + chr(pixels[2][i])
    #         else:
    #             m.append(i)  # Index of pixel to change
    #             m.append(pixels[0][i])  # Pixel red value
    #             m.append(pixels[1][i])  # Pixel green value
    #             m.append(pixels[2][i])  # Pixel blue value
    #     m = m if _is_python_2 else bytes(m)
    #     _sock.sendto(m, (config.settings["configuration"]["UDP_IP"], config.settings["configuration"]["UDP_PORT"]))
    _prev_pixels = np.copy(pixels)


def _update_pi():
    """Writes new LED values to the Raspberry Pi's LED strip

    Raspberry Pi uses the rpi_ws281x to control the LED strip directly.
    This function updates the LED strip with new values.
    """
    global pixels, _prev_pixels
    # Truncate values and cast to integer
    pixels = np.clip(pixels, 0, 255).astype(int)
    # Optional gamma correction
    p = _gamma[pixels] if config.settings["configuration"]["SOFTWARE_GAMMA_CORRECTION"] else np.copy(pixels)
    # Encode 24-bit LED values in 32 bit integers
    r = np.left_shift(p[0][:].astype(int), 8)
    g = np.left_shift(p[1][:].astype(int), 16)
    b = p[2][:].astype(int)
    rgb = np.bitwise_or(np.bitwise_or(r, g), b)
    # Update the pixels
    for i in range(config.settings["configuration"]["N_PIXELS"]):
        # Ignore pixels if they haven't changed (saves bandwidth)
        if np.array_equal(p[:, i], _prev_pixels[:, i]):
            continue
        strip._led_data[i] = rgb[i]
    _prev_pixels = np.copy(p)
    strip.show()

def _update_blinkstick():
    """Writes new LED values to the Blinkstick.
        This function updates the LED strip with new values.
    """
    global pixels
    
    # Truncate values and cast to integer
    pixels = np.clip(pixels, 0, 250).astype(int)
    # Optional gamma correction
    p = _gamma[pixels] if config.settings["configuration"]["SOFTWARE_GAMMA_CORRECTION"] else np.copy(pixels)
    # Read the rgb values
    r = p[0][:].astype(int)
    g = p[1][:].astype(int)
    b = p[2][:].astype(int)

    #create array in which we will store the led states
    newstrip = [None]*(config.settings["configuration"]["N_PIXELS"]*3)

    for i in range(config.settings["configuration"]["N_PIXELS"]):
        # blinkstick uses GRB format
        newstrip[i*3] = g[i]
        newstrip[i*3+1] = r[i]
        newstrip[i*3+2] = b[i]
    #send the data to the blinkstick
    stick.set_led_data(0, newstrip)


def update():
    """Updates the LED strip values"""
    if config.settings["configuration"]["DEVICE"] == 'esp8266':
        _update_esp8266()
    elif config.settings["configuration"]["DEVICE"] == 'pi':
        _update_pi()
    elif config.settings["configuration"]["DEVICE"] == 'blinkstick':
        _update_blinkstick()
    elif config.settings["configuration"]["DEVICE"] == 'stripless':
        pass

# Execute this file to run a LED strand test
# If everything is working, you should see a red, green, and blue pixel scroll
# across the LED strip continously
if __name__.endswith('__main__'):
    import time
    # Turn all pixels off
    pixels *= 0
    pixels[0, 0] = 255  # Set 1st pixel red
    pixels[1, 1] = 255  # Set 2nd pixel green
    pixels[2, 2] = 255  # Set 3rd pixel blue
    print('Starting LED strand test')
    while True:
        pixels = np.roll(pixels, 1, axis=1)
        update()
        time.sleep(.1)
