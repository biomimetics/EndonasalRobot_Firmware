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
import utils_aruco
import utils_force_sensor

is_camera_available = False
# Define the ID of the USB camera
try:
    aruco_detector = utils_aruco.ArucoDetector(camera_id=1)
    if aruco_detector.cap.isOpened():
        is_camera_available = True  
except:
    pass


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
forceStop = threading.Event()
forceStop.clear()
charStart = threading.Event()
charStart.clear()
charStop = threading.Event()
charStop.clear()

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


def generate_pattern1(start, end, inc):
    # Generate the list starting from start, incrementing by inc to end,
    # then decrementing by inc to start
    result = list(np.arange(start, end + inc, inc)) + list(np.arange(end - inc, start, -inc))
    return np.array(result)

def generate_pattern2(start, end, inc1, inc2):
    result = np.array([], dtype=float)
    for current_val in np.arange(start+inc1, end+inc1, inc1):
        result = np.concatenate((result, generate_pattern1(start, current_val, inc2)))
    return result

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

def pressureToPWM(pressure):
    desired_voltage = pressure/67*5
    PWM = desired_voltage/3.3*PWM_PERIOD
    return PWM

def makeSolenoidCmdString(s_vals):
    message_arr = []
    message = b''
    for i, val in enumerate(s_vals):
        if val == 0:
            message += makeCmdString('OUTOFF', i+1)
        elif val == 1:
            message += makeCmdString('OUTON', i+1)
        message_arr.append(message)
        message = b''
    return message_arr

def makePressureCmdString(regulator_vals):
    regulator_vals_pwm = pressureToPWM(regulator_vals)
    message_arr = []
    message = b''
    for i, pwm in enumerate(regulator_vals_pwm):
        message += makeCmdString('PWM{}'.format(i+1), pwm)
        if (i+1)%4 == 0:
            message_arr.append(message)
            message = b''
            # print('msg', message)
            # print('arr', message_arr)
    return message_arr

def makePressureCmd():
    global regulator_vals, solenoid_vals
    message_arr = makePressureCmdString(regulator_vals)
    for message in message_arr:
        sendQ.put(message+b'\n')
    if not (solenoid_vals is None):
        message_arr = makeSolenoidCmdString(solenoid_vals)
        for message in message_arr:
            sendQ.put(message+b'\n')
            time.sleep(0.05)

        #print(message)

offset = 0
def processLine(textLine,index):
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

        if newState.time == 0:
            offset = time.time()-t0

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
    
def camera_thread(q_output):
    if not is_camera_available:
        print("Camera is not available.")
        return
    
    while not cameraStop.is_set():
        if charStart.is_set():
            corners, ids = aruco_detector.detect_frame()
            dumpQ(q_output, 'camera', 'time', time.time() - t0, time.time() - t0,)
        time.sleep(0.01)
    aruco_detector.terminate()
    print('camera saved')

def force_thread(force_sensor, q_output):
    while not forceStop.is_set():
        if charStart.is_set():
            f = force_sensor.read()
            dumpQ(q_output, 'force_sensor', 'force', f, time.time()-t0)
        time.sleep(0.05)
    print('force exited')
def dumpQ(q, component, name, value, time):
    q.put((component,name,value,time))

def input_thread():
    global regulator_vals,solenoid_vals, start_characterization
    while True:
        try:
            input_values = input("Enter values for regulators or solenoids: ")
            val = input_values.split()
            type = str(val[0])
            numericValues = [float(val) for val in input_values.split()[1:]]
            if type == 's':
                if len(numericValues) == 4:
                    solenoid_vals = np.copy(numericValues)
                elif len(numericValues) == 2:
                    solenoid_vals[int(numericValues[0])-1] = numericValues[1]
                print(solenoid_vals)
            elif type == 'r':
                if len(numericValues) == 8:
                    regulator_vals = np.copy(numericValues)
                elif len(numericValues) == 2:
                    regulator_vals[int(numericValues[0])-1] = numericValues[1]
                print(regulator_vals)
            elif type == 'p':
                print('no pressure sensor')
                # print('{0} {1} {2} {3} {4} {5} {6} {7}'.format(sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7, sensor8))
            elif type == 'start':
                charStart.set()
            else:
                print("Invalid number or type of values")

        except ValueError:
            print("Invalid input. Please enter numeric values.")

regulator_vals = np.array([0.] * 8)
solenoid_vals = np.array([0.]* 4)
start_characterization = 0


    
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
    
def main(control_loop, q_output, result_folder, use_force=False):
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
    controlThread =threading.Thread(group=None, target=control_loop, args=(q_output,result_folder), name="controlThread")
    controlThread.daemon = False  # want clean file close
    # controlStop.clear()   
    # for debugging, start control_loop() outside thread
    # control_loop()
    controlThread.start()
# =============================================================================    
    if is_camera_available:
        cameraThread = threading.Thread(group=None, target=camera_thread, name="cameraThread", args=(q_output,))
        cameraStop.clear()
        cameraThread.start()
# =============================================================================
    if use_force:
        force_sensor = utils_force_sensor.ForceSensor('COM4', 115200)
        forceThread = threading.Thread(group=None, target=force_thread, name="forceThread", args=(force_sensor, q_output))
        forceStop.clear()
        forceThread.start()

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
def try_main(*args, **kwargs):
    try:
        main(*args, **kwargs)
    except KeyboardInterrupt as e:
        print('Keyboard Interrupt!')
        sendStop.set()
        rcvStop.set()  # set stop variable for thread
        cameraStop.set()
        forceStop.set()
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
if __name__ == '__main__':
    # q_output = queue.Queue()
    try_main()
    # q_output_list = []
    # while not q_output.empty():
        # q_output_list.append(q_output.get())

    # with open("queue.pickle", "wb") as f:
        # pickle.dump(q_output_list, f)
        
