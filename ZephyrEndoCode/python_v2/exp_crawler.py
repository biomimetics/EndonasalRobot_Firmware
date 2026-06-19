import time
from run_stm_12_v2 import *

default_dwell_time = 1
default_r16_pressure = 20

pressure_map = {
    'f_foot1': 's5',
    'f_foot2': 's6',
    'f_up': 'r3', 
    'f_down': 'r4',
    'f_ext': 'r5',
    
    'm_up': 'r6',
    'm_down': 'r7', 
    'm_ext': 'r8',
    
    'L_foot1': 'r9', 
    'L_foot2': 'r10',
    'L_up': 'r11', 
    'L_down': 'r12',
    'L_ext': 'r13',

    'R_foot1': 'r14',
    'R_foot2': 'r15',
    'R_up': 'r1',
    'R_down': 'r2',
    'R_ext': 's7',
}

pattern_dict = {
    'f_forward': [
        'f_foot2, 20',
        'f_up, 10, f_down, 20, f_ext, 0',
        'f_foot2, 0, f_foot1, 20',
        'f_up, 0, f_down, 0, f_ext, 20',
        'f_foot1, 0, f_ext, 0'
    ],
    'R_backward': [
        'R_foot1, 20',
        'R_up, 5, R_down, 10, R_ext, 0',
        'R_foot1, 0, R_foot2, 20',
        'R_up, 0, R_down, 0, R_ext, 20',
        'R_foot2, 0, R_ext, 0'
    ],
    'R_forward': [
        'R_foot2, 20',
        'R_up, 5, R_down, 5, R_ext, 0',
        'R_foot2, 0',
        'R_foot1, 20',
        'R_up, 0, R_down, 0, R_ext, 8',
        'R_foot1, 0, R_ext, 0'
    ],
    'L_backward': [
        'L_foot1, 20',
        'L_up, 5, L_down, 10, L_ext, 0',
        'L_foot1, 0, L_foot2, 20',
        'L_up, 0, L_down, 0, L_ext, 20',
        'L_foot2, 0, L_ext, 0'
    ],
    'L_forward': [
        'L_foot2, 20',
        'L_up, 5, L_down, 5, L_ext, 0',
        'L_foot2, 0',
        'L_foot1, 20',
        'L_up, 0, L_down, 0, L_ext, 8',
        'L_foot1, 0, L_ext, 0'
    ],
    'pitch_up': [
        'f_foot1, 20',
        'f_ext, 20, f_up, 20',
        'f_foot2, 20',
        'm_up, 20',
        'f_foot1, 0, f_ext, 0, f_up, 0, f_foot2, 0, m_up, 0, m_ext, 8',
    ],
    'turn_left': ['L_backward', 'R_forward'],
    'turn_right': ['L_forward', 'R_backward'],
    'both_forward': ['L_forward', 'R_forward'],
    'both_backward': ['L_backward', 'R_backward'],
    'alL_forward': [
        'L_foot2, 20, R_foot2, 20, L_foot1, 20, R_foot1, 20',
        'm_down, 20',
        'm_down, 0',
        'L_foot2, 0, R_foot2, 0',
        'f_foot1, 20',
        'f_ext, 20, f_up, 20',
        'f_foot2, 20',
    ],
    'flip': [
        'm_down, 20',
        'm_down, 0',
        'L_foot1, 20, R_foot1, 20, L_foot2, 20, R_foot2, 20',
        'L_up, 20, R_up, 20',
        'm_ext, 20'
    ],
    'zero': [
        """f_foot1, 0, f_foot2, 0, f_up, 0, f_down, 0, f_ext, 0, 
        m_up, 0, m_down, 0, m_ext, 0, 
        L_foot1, 0, L_foot2, 0, L_up, 0, L_down, 0, L_ext, 0, 
        R_foot1, 0, R_foot2, 0, R_up, 0, R_down, 0, R_ext, 0
        """
    ]
}

def control_loop(q_output, result_folder): 
    global regulator_vals, solenoid_vals
    global charStart
    i = 0
    state = StateStruct()
    print('control_loop- waiting for STM32READY\n')
    time.sleep(1)    # check periodically for start    
    while controlStop.is_set():
        time.sleep(1)    # check periodically for start    
    makeCmd('PRNWAIT', 1000)   # set wait time for state update in ms
    time.sleep(3)
    print('control_loop: started thread')

    makePressureCmd()
    
    while (not controlStop.is_set()):
        if not stateQ.empty():
            if not charStart.is_set():
                makePressureCmd()
                time.sleep(1)  # should run at state update rate                
            else:
                print("characterization starts")
                for i in range(100):
                    print('trial', i)
                    # print("setting backbone to " +str(backbone_pressure)+ " PSI)")
                    for j, cur_pattern in enumerate(pattern):
                        # print("setting actuator to " +str(actuator_pressure)+ " PSI)")
                        state = stateQ.get()

                        for ii in range(len(regulator_vals)):
                            regulator_vals[ii] = cur_pattern[0][ii]
                        for ii in range(len(solenoid_vals)):
                            solenoid_vals[ii] = cur_pattern[1][ii]

                        print(f'step {j}')

                        makePressureCmd()
                        for i, val in enumerate(regulator_vals):
                            dumpQ(q_output, 'regulator', 'PWM{}'.format(i+1), val, time.time()-t0)
                        time.sleep(time_per_step)
                        if controlStop.is_set():
                            break
                    dumpQ(q_output, 'info', 'CYCLE_DONE', i, time.time()-t0)
                    if controlStop.is_set():
                        break
                charStart.clear()
                q_output_list = []
                while not q_output.empty():
                    q_output_list.append(q_output.get())

                with open(os.path.join(result_folder, "queue.pickle"), "wb") as f:
                    pickle.dump(q_output_list, f)
                print('queue saved')
                controlStop.set() # stop program after done characterization
        else:
#            print('stateQ empty')
            # print("waiting for characterization start")
            time.sleep(1)

    print('control_loop: finished thread')
    
    cameraStop.set()

if __name__ == '__main__':
    import argparse
    import json
    import os
    import utils
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default='./data-raw')
    parser.add_argument("--run_name", default='test')
    parser.add_argument('--comment', default="")
    parser.add_argument("--debug", action='store_true')

    args = parser.parse_args()
    args.run_name = os.path.splitext(os.path.basename(__file__))[0]
    result_folder = utils.create_runs_folder(args)
    if is_camera_available:
        aruco_detector.start_video(result_folder)

    q_output = queue.Queue()
    regulator_vals[15] = default_r16_pressure
    try_main(
        control_loop,
        q_output,
        result_folder,
        pattern_dict=pattern_dict,
        pressure_map=pressure_map,
        default_dwell_time=default_dwell_time
    )
