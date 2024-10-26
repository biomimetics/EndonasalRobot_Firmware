# -*- coding: utf-8 -*-
"""
Created on Tue Jul 18 15:08:32 2023

@author: ronf
"""

# testing whether ser.readline and ser.write read eachother (line is echoing)

import serial
from serial.tools import list_ports
# list_ports.comports()  # Outputs list of available serial ports
print('ports being used:')
print([port.device for port in serial.tools.list_ports.comports()])

