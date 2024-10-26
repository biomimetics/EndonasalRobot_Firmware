import numpy as np
import serial
import time
from time import sleep
import csv
import sys
import threading
from queue import Queue
from queue import LifoQueue
import cv2
import cv2.aruco as aruco
import numpy as np
import queue
import pickle

def detect_aruco_tag(frame):
    #dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
    parameters =  aruco.DetectorParameters()
    # parameters.adaptiveThreshConstant=1
    detector = aruco.ArucoDetector(dictionary, parameters)
    return detector.detectMarkers(frame)

is_camera_available = False
# Define the ID of the USB camera
camera_id = 1
# Create a VideoCapture object to capture images from the camera
cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)                       
# Check if the camera is opened successfully
if cap.isOpened():
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    is_camera_available = True  
else:
    print("Unable to open the camera.")


init_corners=None

sendQ = Queue()
stateQ = LifoQueue()  # keeping track of remote state
# always use newest data
start_time = time.time()

SystemCoreClock = 16000000
PWM_FREQUENCY = 2000
PWM_PERIOD = ((SystemCoreClock / PWM_FREQUENCY) - 1)*6

from serial.tools import list_ports
# list_ports.comports()  # Outputs list of available serial ports
print('ports being used:')
print([port.device for port in serial.tools.list_ports.comports()])

#### CONSTANTS ###########
data_file_name = '../Data/data.txt'
telemetry = False
numSamples = 20 # 1 kHz sampling in pid loop = 3 sec
INTERVAL = 0.1  # update rate for state information


rcvStop = threading.Event()
rcvStop.clear()
sendStop = threading.Event()
sendStop.clear()
controlStop = threading.Event()
controlStop.clear()
cameraStop = threading.Event()
cameraStop.clear()

ser = serial.Serial('COM3')
ser.baudrate=230400

class StateStruct():
    def __init__(self):
        self.time = 0.0
        self.hx711 = 0  # load cell
        self.qdec3 = 0  # quad decoder using timer 3
        self.qdec5 = 0  # quadrature decoder using timer 5
        self.adc8 = 0   #2 12 bit A/D channels 8 to 15
        self.adc9 = 0 #5
        self.adc10 = 0 #3
        self.adc11 = 0 #1
        self.adc12 = 0
        self.adc13 = 0 
        self.adc14 = 0 #4
        self.adc15 = 0


# 
def convertADC(adc):
    return adc/4095*3.3

def convertGagePressureSmall(voltage):
    if voltage != 0:
        voltage = voltage/0.673
        return (voltage-0.5)*15
    else: return

def setDisplacement(displacement, maxDis):
    pressure = displacement/maxDis*10+5
    return pressure

def setPressure(pressure):
    desired_voltage = pressure/67*5
    PWM = desired_voltage/3.3*PWM_PERIOD
    return PWM

offset = 0
def processLine(textLine,index):
    global sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7, sensor8
    global offset
    newState = StateStruct()    
    #  "t=","hx711","qdec3","qdec4", "adc8","adc9","adc10", "adc11","adc12","adc13","adc14","adc15"
    data = textLine.split(',')  # split on comma
    # print('data ', data)
    # print('textline ', textLine)
   # split first element on space delimiter to find #, which indicates a comment
    firstChar = data[0].split()
    if (firstChar[0] == '#') or (firstChar[0] == '***'):
 #           print(textLine)
             # check here for # STM32READY before enabling control_loop
            if(firstChar[1] == 'STM32READY'):  
                controlStop.clear()   # only start control loop if get STM32READY message
    else:
        # print(textLine)
        temp=np.zeros(np.size(data))
        for i in range(0,np.size(data)):
            temp[i] = float(data[i])
        
        newState.time = temp[0]
        newState.hx711 = temp[1]  
        newState.qdec3 = temp[2]  
        newState.qdec5 = temp[3]  
        newState.adc8 = temp[4]   
        newState.adc9 = temp[5]
        newState.adc10 = temp[6]
        newState.adc11 = temp[7]
        newState.adc12 = temp[8]
        newState.adc13 = temp[9]
        newState.adc14 = temp[10]
        newState.adc15 = temp[11]
        

        
        stateQ.put(newState)
        # print('hi this is adc8: ')
        # print(stateQ.get().adc8)
        
  #      if (index %100) == 0:
  #          print(index, end=',')
        #print("adc11 value:", convertADC(newState.adc11))

        if newState.time == 0:
            offset = time.time()-t0
        sensor1 = convertGagePressureSmall(convertADC(newState.adc11))
        # print("sensor1RAW: " + str(convertADC(newState.adc11)))
        # print("sensor1: " + str(sensor1))
        
        sensor2 = convertGagePressureSmall(convertADC(newState.adc8))
        # print("sensor2RAW: " + str(convertADC(newState.adc8)))
        # print("sensor2: " + str(sensor2))
        
        sensor3 = convertGagePressureSmall(convertADC(newState.adc10))
        # print("sensor3RAW: " + str(convertADC(newState.adc10)))
        # print("sensor3: " + str(sensor3))
        
        sensor4 = convertGagePressureSmall(convertADC(newState.adc14))
        # print("sensor4RAW: " + str(convertADC(newState.adc14)))
        # print("sensor4: " + str(sensor4))
        
        sensor5 = convertGagePressureSmall(convertADC(newState.adc9)) #problem
        # print("sensor5RAW: " + str(convertADC(newState.adc9)))
        # print("sensor5: " + str(sensor5))
        
        sensor6 = convertGagePressureSmall(convertADC(newState.adc12)) #problem
        # print("sensor6RAW: " + str(convertADC(newState.adc12)))        
        # print("sensor6: " + str(sensor6))
        
        sensor7 = convertGagePressureSmall(convertADC(newState.adc13)) #Problem
        # print("sensor7RAW: " + str(convertADC(newState.adc13)))        
        # print("sensor7: " + str(sensor7))
        
        sensor8 = convertGagePressureSmall(convertADC(newState.adc15))
        # print("sensor8RAW: " + str(convertADC(newState.adc15)))       
        # print("sensor8: " + str(sensor8))

        if sensor1 != None:
            dumpQ('sensor','sensor1', sensor1, newState.time+offset)
            #print(sensor1)
        if sensor2 != None:
            dumpQ('sensor','sensor2', sensor2, newState.time+offset)
        if sensor3 != None:
            dumpQ('sensor','sensor3', sensor3, newState.time+offset)
        if sensor4 != None:
            dumpQ('sensor','sensor4', sensor4, newState.time+offset)
        if sensor5 != None:
            dumpQ('sensor','sensor5', sensor5, newState.time+offset)
        if sensor6 != None:
            dumpQ('sensor','sensor6', sensor6, newState.time+offset)
        if sensor7 != None:
            dumpQ('sensor','sensor7', sensor7, newState.time+offset)
        if sensor8 != None:
            dumpQ('sensor','sensor8', sensor8, newState.time+offset)

# thread receive state message from USB (STM32)
def rcvstate():
    print('Started rcvstate thread')
    writeFileHeader(data_file_name)
    fileout = open(data_file_name,'a') # append data to file
    if ser.isOpen():
        print("Serial open. Using port %s and baudrate %s" % (ser.name, ser.baudrate))
    else:
        print('serial open failed. Exiting.')
        exit()
   
    ser.reset_input_buffer() # get rid of accumulated inputs
    ser.flush()  # get rid of any extra outputs
    line = ser.readline()  # throw out first line read which is *** Booting Zephyr OS ***
    index = 0
    while not rcvStop.is_set():
        line = ser.readline()
        #print("raw line = %s" %(line))
        line = line.decode('ascii')   # read one \n terminated line, convert to string
        line = line.replace("\n","")  # replace extra line feed (leave \r in place)
 #       print('rcv index:%d. StateQ size %d\t%s' %(index,stateQ.qsize(),line))
        fileout.write(str(line))
        processLine(line, index)  # convert text to state values, and place in stateQ
#        sleep(INTERVAL)   #don't delay, otherwise serial will be out of sync with control thread
        index +=1
        time.sleep(0.001)  # give up thread for other threads to run
    print("rcvstate: Closing file")
    fileout.close()
    print("rcvstate: Closing serial in 2 seconds")
    time.sleep(2)
    ser.close() # should be in receive thread so it closes after reading whole line
    print('rcvstate: finished thread')

# thread for sending commands over USB to STM32
# use queue so can send commands from multiple sources
def sendCmd():
   i=0
   print('sendCMD: started thread') 
   while not sendQ.empty():
       message = sendQ.get()  # flush any initial message command queue
   while not sendStop.is_set():
       time.sleep(0.001)   # give other threads time to run
       if not sendQ.empty():
       # get message if any from command queue
           message = sendQ.get()
#           print('sendCmd %d: message=%s' % (i, message))
           ser.write(message)   # send text to STM32, format is command word in text followed by short
           i=i+1 
   print('sendCmd: finished thread')

def makeCmd(command, value):
    textval = "{0}".format("%-6d" % value)  # convert command value to string, left justify
    messageString = command.encode('utf8') + b' '+ textval.encode('utf8') +b'\n'
    sendQ.put(messageString)
    
def makeCmdString(command, value):
    textval = "{0}".format("%-6d" % value)  # convert command value to string, left justify
    messageString = command.encode('utf8') + b' '+ textval.encode('utf8')
    return(messageString)
    
def getaruco():
    if not is_camera_available:
        print("Camera is not available.")
        return
    
    while not cameraStop.is_set():
        #print("hi i am detecting")f
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture the image.")
        aruco_info = ""
        corners, ids, c = detect_aruco_tag(frame)
        #aruco.drawDetectedMarkers(frame, corners, ids)
        # if ids is not None:
        #     print("ID detected")
        #     for i in range(len(ids)):
        #         print(f"id: {ids[i][0]}; {corners[i][0][0]}, {corners[i][0][1]}, {corners[i][0][2]}, {corners[i][0][3]}")
        #         aruco_info += f" {ids[i][0]}: {corners[i][0][0]}, {corners[i][0][1]}, {corners[i][0][2]}, {corners[i][0][3]};"
        #cv2.imshow("Image", frame)
        if ids is not None:
            for i in range(len(ids)):
                #print(f"id: {ids[i][0]}; {corners[i][0][0]}, {corners[i][0][1]}, {corners[i][0][2]}, {corners[i][0][3]}")
                dumpQ('camera', str(ids[i][0]), [corners[i]], time.time()-t0)
            #q_output.put(('aruco', [corners, ids], time.time()-t0))
        time.sleep(0.01)

def dumpQ(component, name, value, time):
    q_output.put((component,name,value,time))

def input_thread():
    global regulator1, regulator2, regulator3, regulator4, regulator5, regulator6, regulator7, regulator8
    global solenoid1, solenoid2, solenoid3, solenoid4
    global sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7, sensor8
    while True:
        try:
            input_values = input("Enter values for regulators or solenoids: ")
            val = input_values.split()
            type = str(val[0])
            numericValues = [float(val) for val in input_values.split()[1:]]
            if type == 's':
                ns1, ns2, ns3, ns4 = numericValues
                solenoid1 = ns1
                solenoid2 = ns2
                solenoid3 = ns3
                solenoid4 = ns4
            elif type == 'r':
                new_regulator1, new_regulator2, new_regulator3, new_regulator4, new_regulator5, new_regulator6, new_regulator7, new_regulator8 = numericValues
                regulator1 = new_regulator1
                regulator2 = new_regulator2
                regulator3 = new_regulator3
                regulator4 = new_regulator4
                regulator5 = new_regulator5
                regulator6 = new_regulator6
                regulator7 = new_regulator7
                regulator8 = new_regulator8
            elif type == 'p':
                print('{0} {1} {2} {3} {4} {5} {6} {7}'.format(sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7, sensor8))
            else:
                print("Invalid number or type of values")

        except ValueError:
            print("Invalid input. Please enter numeric values.")

regulator1 = 0
regulator2 = 0
regulator3 = 0
regulator4 = 0
regulator5 = 0
regulator6 = 0
regulator7 = 0
regulator8 = 0
solenoid1 = 0
solenoid2 = 0
solenoid3 = 0
solenoid4 = 0
sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7, sensor8 = (None, None, None, None, None, None, None, None)
start_characterization = 0


def control_loop(): 
    global regulator1, regulator2, regulator3, regulator4, regulator5, regulator6, regulator7, regulator8
    global solenoid1, solenoid2, solenoid3, solenoid4
    global start_characterization
    i = 0;
    state = StateStruct()
    print('control_loop- waiting for STM32READY\n')
    # makeCmd('PRNTWAIT', 5000)   # set wait time for state update in ms
    time.sleep(1)    # check periodically for start    
    while controlStop.is_set():
        time.sleep(1)    # check periodically for start    
    makeCmd('PRNWAIT', 1000)   # set wait time for state update in ms
    time.sleep(3)
    print('control_loop: started thread')

    #Initialize Pressure Regulators
    pressure_value1 = setPressure(regulator1)
    pressure_value2 = setPressure(regulator2)
    pressure_value3 = setPressure(regulator3)
    pressure_value4 = setPressure(regulator4)

    max__actuator_pressure = 20
    max_backbone_pressure = 10

    pattern = []

    # Loop through the range from 1 to start_value (inclusive)
    for i in range(1, max__actuator_pressure + 1):
        # Append 0 and the current value to the pattern
        pattern.append(0)
        pattern.append(i)
    pattern.append(0)

    # Print the pattern
    print(pattern)

    while (not controlStop.is_set()):
        if not stateQ.empty() and start_characterization == 1:
            print("characterization starts")
            for backbone_pressure in range(max_backbone_pressure + 1):
                print("setting backbone to " +str(backbone_pressure)+ " PSI)")
                for actuator_pressure in pattern:
                    print("setting actuator to " +str(actuator_pressure)+ " PSI)")

                    state = stateQ.get()
                    pressure_value1 = setPressure(backbone_pressure)
                    pressure_value2 = setPressure(actuator_pressure)
                    # pressure_value3 = setPressure(regulator3)
                    # pressure_value4 = setPressure(regulator4)
                    message = makeCmdString('PWM1', pressure_value1) + makeCmdString('PWM2', pressure_value2) #+ makeCmdString('PWM3', pressure_value3) + makeCmdString('PWM4', pressure_value4) 
                    sendQ.put(message+b'\n')
                    dumpQ('regulator', 'PWM1', regulator1, time.time()-t0)
                    dumpQ('regulator', 'PWM2', regulator2, time.time()-t0)
                    # dumpQ('regulator', 'PWM3', regulator3, time.time()-t0)
                    # dumpQ('regulator', 'PWM4', regulator4, time.time()-t0)
                    # dumpQ('regulator', 'PWM5', regulator5, time.time()-t0)
                    # dumpQ('regulator', 'PWM6', regulator6, time.time()-t0)
                    # dumpQ('regulator', 'PWM7', regulator7, time.time()-t0)
                    # dumpQ('regulator', 'PWM8', regulator8, time.time()-t0)
                    time.sleep(1)  # should run at state update rate
        else:
#            print('stateQ empty')
            print("waiting for characterization start")
            time.sleep(1)

    print('control_loop: finished thread')
    cameraStop.set()
    
def writeFileHeader(dataFileName):
    fileout = open(dataFileName,'w')
    #write out parameters in format which can be imported to Excel
    today = time.localtime()
    date = str(today.tm_year)+'/'+str(today.tm_mon)+'/'+str(today.tm_mday)+'  '
    date = date + str(today.tm_hour) +':' + str(today.tm_min)+':'+str(today.tm_sec)
    fileout.write('"Data file recorded ' + date + '"\n')
    fileout.write('" time  hx711, qdec3, qdec5, adc8,  adc9, adc10, adc11, adc12, adc13, adc14, adc15"\n')
    fileout.close()

# debug version- debugger has trouble with threads
def main_test():
    print("Data Logging for STM32, with USB connection- test threads\n")
    rcvStop.clear()
    rcvstate()   # run directly for debugging outside thread
    
def main():
    print("Data Logging for STM32, with USB connection\n")
    stateThread = threading.Thread(group=None, target=rcvstate, name="stateThread")
    stateThread.daemon = False  # want clean file close
    rcvStop.clear()
    stateThread.start()
    time.sleep(5)  # give time to catch up with printing

# =============================================================================
#   be ready to send commands when control thread starts  
    sendThread =threading.Thread(group=None, target=sendCmd, name="sendThread")
    sendThread.daemon = False  # want clean file close
    sendStop.clear()
    sendThread.start()
    time.sleep(2) # give time before control thread starts
# =============================================================================
    controlStop.set()  # only start control loop if get STM32READY message
    controlThread =threading.Thread(group=None, target=control_loop, name="controlThread")
    controlThread.daemon = False  # want clean file close
    # controlStop.clear()   
    # for debugging, start control_loop() outside thread
    # control_loop()
    controlThread.start()
# =============================================================================    
    if is_camera_available:
        cameraThread = threading.Thread(group=None, target=getaruco, name="camerathread")
        cameraStop.clear()
        cameraThread.start()
# =============================================================================
    userThread = threading.Thread(target=input_thread, daemon=True)
    userThread.start()

    print('Threads started. ctrl C to quit')
    # print(threading.enumerate())
    # Loop infinitely waiting for commands or until the user types quit or ctrl-c
    while True:
         #### if keyboard input is needed, it should be in thread to avoid blocking
        # Read keyboard input from the user
# =============================================================================
#         if (sys.version_info > (3, 0)):
#             message = input('')  # Python 3 compatibility
#         else:
#             message = raw_input('')  # Python 2 compatibility
# #        print('input message=%s' %(message))
#         # If user types quit then lets exit and close the socket
#         if 'quit' in message:
#             print("begin quit")
#             rcvStop.set()  # set stop variable
#             break
#         else:
#             sendQ.put(message.encode('utf8')+b'\n\r')
# =============================================================================
        time.sleep(0.5)  # give threads time to run
    print('Quit keyboard input loop')
    
  
    print("End of main. Closing threads")
    sendStop.set()
    rcvStop.set()  # set stop variable for thread
    controlStop.set()
    sleep(1.0) # wait for threads to close
    stateThread.join()   # wait for termination of state thread    
    sendThread.join()
    controlThread.join()
#    exit()      
#    sys.exit()
    
t0 = time.time()
#Provide a try-except over the whole main function
# for clean exit. 
if __name__ == '__main__':
    q_output = queue.Queue()
    try:
        main()
    except KeyboardInterrupt as e:
        print('Keyboard Interrupt!')
        sendStop.set()
        rcvStop.set()  # set stop variable for thread
        cameraStop.set()
        controlStop.set()
        sleep(3.0) # wait for threads to close
        ser.close()
    except OSError as error:
        print(error)     # the exception instance
        print(error.args)      # arguments stored in .args
        print("IO Error.")
        ser.close()
    finally:
        ser.close()
        print("normal exit")
        # should also close file
 #       exit()
    q_output_list = []
    while not q_output.empty():
        q_output_list.append(q_output.get())

    with open("queue.pickle", "wb") as f:
        pickle.dump(q_output_list, f)
        
