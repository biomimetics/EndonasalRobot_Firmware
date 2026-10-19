#  Record MLX90393 magnetometer data from the STM32 (Zephyr) over USB to file
#  Same interface as ZephyrEndoCode/python/control-record.py
#
#  Usage:  python mag-record.py [PORT]      e.g.  python mag-record.py COM3
#  With no PORT the ST-Link virtual COM port is found automatically.
#  Start the script, then press RESET on the STM32 (or start it while holding
#  RESET and release) until "control_loop: started" appears. ctrl-C to quit.

import os
import sys
import time
import threading
from queue import Queue, LifoQueue

import numpy as np
import serial
from serial.tools import list_ports

sendQ = Queue()
stateQ = LifoQueue()  # keeping track of remote state, always use newest data

#### CONSTANTS ###########
BAUDRATE = 230400
PRNWAIT = 100       # ms between state updates from STM32 (sensors give ~1 per 120 ms)
PRINT_EVERY = 10    # print every Nth state to the terminal
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Data')
data_file_name = os.path.join(DATA_DIR, time.strftime('mag-%Y%m%d-%H%M%S.txt'))

rcvStop = threading.Event()
sendStop = threading.Event()
controlStop = threading.Event()
stm32Ready = threading.Event()


def find_port():
    if len(sys.argv) > 1:
        return sys.argv[1]
    ports = list_ports.comports()
    print('ports available:', [p.device for p in ports])
    for p in ports:
        if p.vid == 0x0483:  # STMicroelectronics (ST-Link virtual COM port)
            return p.device
    return 'COM3'


ser = serial.Serial(find_port(), BAUDRATE, timeout=0.5)


class StateStruct():
    def __init__(self):
        self.time = 0.0
        self.mag1 = np.zeros(3)  # MAG1 (I2C1) x, y, z in gauss, calibrated
        self.mag2 = np.zeros(3)  # MAG2 (I2C2) x, y, z in gauss, calibrated

    @property
    def diff(self):  # field difference MAG2 - MAG1
        return self.mag2 - self.mag1


#  t, mag1_x, mag1_y, mag1_z, mag2_x, mag2_y, mag2_z
def processLine(textLine):
    textLine = textLine.strip()
    if not textLine:
        return
    if textLine.startswith('#') or textLine.startswith('***'):
        print(textLine)  # comment from STM32
        if textLine.split()[1:2] == ['STM32READY']:
            stm32Ready.set()
        return
    try:
        temp = [float(v) for v in textLine.split(',')]  # 'nan' = sensor read error
    except ValueError:
        print('bad line: %s' % textLine)
        return
    if len(temp) != 7:
        print('bad line: %s' % textLine)
        return
    newState = StateStruct()
    newState.time = temp[0]
    newState.mag1 = np.array(temp[1:4])
    newState.mag2 = np.array(temp[4:7])
    stateQ.put(newState)


# thread receive state message from USB (STM32)
def rcvstate():
    print('Started rcvstate thread')
    writeFileHeader(data_file_name)
    print("Serial open. Using port %s and baudrate %s" % (ser.name, ser.baudrate))
    ser.reset_input_buffer()  # get rid of accumulated inputs
    with open(data_file_name, 'a') as fileout:  # append data to file
        while not rcvStop.is_set():
            line = ser.readline()  # returns b'' on timeout so stop is checked
            if not line:
                continue
            line = line.decode('ascii', errors='replace').replace('\r', '')
            fileout.write(line)
            processLine(line)  # convert text to state values, and place in stateQ
    print('rcvstate: finished thread, data in %s' % data_file_name)


# thread for sending commands over USB to STM32
# use queue so can send commands from multiple sources
def sendCmd():
    print('sendCmd: started thread')
    while not sendStop.is_set():
        if not sendQ.empty():
            message = sendQ.get()
            print('sendCmd: message=%s' % message)
            ser.write(message)
        time.sleep(0.001)
    print('sendCmd: finished thread')


def makeCmdString(command, value=0):
    return command.encode('utf8') + b' ' + ('%-6d' % value).encode('utf8')


def makeCmd(command, value=0):
    sendQ.put(makeCmdString(command, value) + b'\n')


def control_loop():
    print('control_loop: waiting for STM32READY (press RESET on STM32)')
    while not stm32Ready.wait(0.5):
        if controlStop.is_set():
            return
    makeCmd('PRNWAIT', PRNWAIT)  # set wait time for state update in ms
    # makeCmd('CALIB')           # uncomment to run six-position calibration at start
    print('control_loop: started')
    i = 0
    while not controlStop.is_set():
        if stateQ.empty():
            time.sleep(0.001)
            continue
        state = stateQ.get()
        with stateQ.mutex:
            stateQ.queue.clear()  # LIFO: drop older states, keep newest
        # ---- add control / experiment code here, using state.mag1, state.mag2 ----
        if i % PRINT_EVERY == 0:
            print('t=%8.3f  MAG1 %s |B|=%.4f  MAG2 %s |B|=%.4f  |dB|=%.4f G' % (
                state.time,
                np.array2string(state.mag1, precision=4, floatmode='fixed'),
                np.linalg.norm(state.mag1),
                np.array2string(state.mag2, precision=4, floatmode='fixed'),
                np.linalg.norm(state.mag2),
                np.linalg.norm(state.diff)))
        i += 1
    print('control_loop: finished thread')


def writeFileHeader(dataFileName):
    os.makedirs(os.path.dirname(dataFileName), exist_ok=True)
    with open(dataFileName, 'w') as fileout:
        fileout.write('"Data file recorded ' + time.strftime('%Y/%m/%d  %H:%M:%S') + '"\n')
        fileout.write('" time, mag1_x, mag1_y, mag1_z, mag2_x, mag2_y, mag2_z (gauss)"\n')


def stopAll():
    controlStop.set()
    sendStop.set()
    rcvStop.set()


def main():
    print("Magnetometer data logging for STM32, with USB connection\n")
    threads = [threading.Thread(target=f, name=f.__name__)
               for f in (rcvstate, sendCmd, control_loop)]
    for t in threads:
        t.start()
    print('Threads started. ctrl C to quit')
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('Keyboard Interrupt!')
    finally:
        stopAll()
        for t in threads:
            t.join()
        ser.close()
        print("normal exit")


if __name__ == '__main__':
    main()
