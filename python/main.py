from __future__ import print_function
from __future__ import division
from scipy.ndimage.filters import gaussian_filter1d
from collections import deque
import time
import sys
import numpy as np
import config
import lib.microphone as microphone
from lib.dsp import ExpFilter
#import lib.led as led
import lib.devices as devices
import lib.bottle as bottle
import logging
import subprocess
from threading import Thread
import datetime
import lib.api as api
import random
import socket
import util
from visualizer import Visualizer
from lib.dsp import DSP
from lib.viot import viot

class Board():
    def __init__(self, board):
        self.board = board
        self.config = config.settings["devices"][board]["configuration"]
        self.effectConfig = config.settings["devices"][board]["effect_opts"]
        self.visualizer = Visualizer(self)
        self.signalProcessor = DSP(self)
    
        self.esp = devices.ESP8266(
            ip            = self.config["UDP_IP"],
            port          = self.config["UDP_PORT"],
            leds          = self.config["N_PIXELS"]
        )


def frames_per_second():
    """ Return the estimated frames per second

    Returns the current estimate for frames-per-second (FPS).
    FPS is estimated by measured the amount of time that has elapsed since
    this function was previously called. The FPS estimate is low-pass filtered
    to reduce noise.

    This function is intended to be called one time for every iteration of
    the program's main loop.

    Returns
    -------
    fps : float
        Estimated frames-per-second. This value is low-pass filtered
        to reduce noise.
    """
    global _time_prev, _fps
    time_now = time.time() * 1000.0
    dt = time_now - _time_prev
    _time_prev = time_now
    if dt == 0.0:
        return _fps.value
    return _fps.update(1000.0 / dt)


#### HACK for laser ####
import socket
laserSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)





def microphone_update(audio_samples):
    global y_roll, prev_rms, prev_exp, prev_fps_update

    syncBoard = next(iter(boards))
    for board in boards:
        if(boards[syncBoard].config["N_PIXELS"] < boards[board].config["N_PIXELS"]):
            syncBoard = board
    
    # Get processed audio data for each device
    audio_datas = {}
    for board in boards:
        audio_datas[board] = boards[board].signalProcessor.update(audio_samples)
        
    outputs = {}

    def renderBoard(board):
        audio_input = audio_datas[board]["vol"] > config.settings["configuration"]["MIN_VOLUME_THRESHOLD"]
        outputs[board] = boards[board].visualizer.get_vis(audio_datas[board]["mel"], audio_input)


        if(boards[board].config["current_effect"] in boards[board].effectConfig and "delay" in boards[board].effectConfig[boards[board].config["current_effect"]]):
            time.sleep(boards[board].effectConfig[boards[board].config["current_effect"]]["delay"])

        outputs[board][0] = outputs[board][0] * config.settings["brightness"]
        outputs[board][1] = outputs[board][1] * config.settings["brightness"]
        outputs[board][2] = outputs[board][2] * config.settings["brightness"]

    if(config.settings["sync"]):
        renderBoard(syncBoard)
        for board in boards:
            boards[board].esp.show(outputs[syncBoard])
    else:
        for board in boards:
            renderBoard(board)
            boards[board].esp.show(outputs[board])

    # FPS update
    fps = frames_per_second()
    if time.time() - 0.5 > prev_fps_update:
        prev_fps_update = time.time()

    # if config.settings["configuration"]["displayFPS"]:
    #print('FPS {:.0f} / {:.0f}'.format(fps, config.settings["configuration"]["FPS"]))



boards = {}
for board in config.settings["devices"]:
    boards[board] = Board(board)

prev_fps_update = time.time()
# The previous time that the frames_per_second() function was called
_time_prev = time.time() * 1000.0
# The low-pass filter used to estimate frames-per-second
_fps = ExpFilter(val=config.settings["configuration"]["FPS"], alpha_decay=0.2, alpha_rise=0.2)




apiThread = None

api.setBoards(boards)
api.setConfig(config)

def doStream():
    microphone.start_stream(microphone_update)


if __name__ == "__main__":
    streamThread = Thread(target=doStream)
    streamThread.start()
