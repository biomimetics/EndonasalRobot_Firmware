import time
from run_stm_12_v2 import *

default_dwell_time = 1
default_r16_pressure = 12


pressure_map = {
    'f_f1': 's1',
    'f_f2': 's2',
    'f_up': 'r2', 
    'f_down': 'r1',
    'f_ext': 'r3',
    
    'm_up': 'r5',
    'm_down': 'r4', 
    'm_ext': 'r6',
    
    'r_f1': 's5', 
    'r_f2': 's6',
    'r_up': 'r8', 
    'r_down': 'r7',
    'r_ext': 'r9',

    'l_f1': 's3',
    'l_f2': 's4',
    'l_up': 'r11',
    'l_down': 'r10',
    'l_ext': 'r12',
}

#upside down

# pressure_map = {
#     'f_f1': 's1',
#     'f_f2': 's2',
#     'f_down': 'r2', 
#     'f_up': 'r1',
#     'f_ext': 'r3',
    
#     'm_down': 'r5',
#     'm_up': 'r4', 
#     'm_ext': 'r6', step 5 / 6

    
#     'l_f1': 's5', 
#     'l_f2': 's6',
#     'l_down': 'r8', 
#     'l_up': 'r7',
#     'l_ext': 'r9',
2
#     'r_f1': 's3',
#     'r_f2': 's4',
#     'r_down': 'r11',
#     'r_up': 'r10',
#     'r_ext': 'r12',
# }


pattern_dict = {
    'pull': [
        'l_f1, 15, r_f2, 15, l_f2, 15, r_f1, 15, 1',
        'm_up, 8, 3',
        'm_up, 0',
        'l_f1, 0, r_f2, 0, l_f2, 0, r_f1, 0, 1',
        
    ],
    'f_pitchup': [
      'f_f1, 15, f_f2, 15, f_down, 10, 1',
      'm_ext, 10,2',
      'm_up, 10,0.5',
      'f_f1, 0, f_f2, 0, f_down, 0, m_up, 2, m_ext, 0, 1',


    ],
    'f_forward': [
        'f_f2, 15,0.5',
        # 'f_up, 10, f_down, 0, f_ext, 0,1',
        'f_up, 5, f_down, 10, f_ext, 0,0.5',
        'f_f2, 0,0.5', 
        'f_f1, 15, 0.3',
        'f_up, 0, f_down, 0, f_ext, 15,0.5',
        'f_f1, 0, f_ext, 0,0.1'
    ],
    'f_forward_slow': [
        'f_f2, 15',
        'f_up, 0, f_down, 15, f_ext, 0',
        'f_f2, 0', 
        'f_f1, 15',
        'f_up, 0, f_down, 0, f_ext, 15',
        'f_f1, 0, f_ext, 0,0.3'
    ],
    'R_backward': [
        'R_f1, 15,0.3',
        'R_up, 5, R_down, 13, R_ext, 0, 0.3',
        'R_f1, 0,0.3',
        'R_f2, 15,0.3',
        'R_up, 0, R_down, 0, R_ext, 15,0.3',
        'R_f2, 0, R_ext, 0, R_down, 0, 0.3'
    ],
    'L_backward': [
        'L_f1, 15,0.3',
        'L_up, 5, L_down, 13, L_ext, 0, 0.3',
        'L_f1, 0,0.3',
        'L_f2, 15,0.3',
        'L_up, 0, L_down, 0, L_ext, 15,0.3',
        'L_f2, 0, L_ext, 0, L_down, 0, 0.3'
    ],
    'R_forward': [
        'R_f2, 15,0.3',
        'R_up, 5, R_down, 13, R_ext, 0, 0.3',
        'R_f2, 0,0.3',
        'R_f1, 15,0.3',
        'R_up, 0, R_down, 0, R_ext, 15,0.3',
        'R_f1, 0, R_ext, 0, R_down, 0, 0.3'
    ],
    'L_forward': [
        'L_f2, 15,0.3',
        'L_up, 5, l_down, 13, L_ext, 0, 0.3',
        'L_f2, 0,0.3',
        'L_f1, 15,0.3',
        'L_up, 0, L_down, 0, L_ext, 15,0.3',
        'L_f1, 0, L_ext, 0,l_down, 0, 0.3'
    ],
    'pitch_up': [
        'f_f1, 15, 2',
        'f_ext, 15, f_up, 15, 5',
        'f_f2, 15',
        'm_ext, 15, m_up, 10, 1',
        'f_f1, 0, f_ext, 0, f_up, 0, f_f2, 0, m_up, 0, m_ext, 8',
    ],
    'turn_left': ['L_backward', 'R_forward'],
    'turn_right': ['L_forward', 'R_backward'],
    'both_forward': ['L_forward', 'R_forward'],
    'all_forward': [
        'l_forward', 'r_forward', 'f_forward'
    ],
    'both_backward': ['L_backward', 'R_backward'],
    # 'alL_forward': [
    #     'L_f2, 15, R_f2, 15, L_f1, 15, R_f1, 15',
    #     'm_down, 15',
    #     'm_down, 0',
    #     'L_f2, 0, R_f2, 0',
    #     'f_f1, 15',
    #     'f_ext, 15, f_up, 15',
    #     'f_f2, 15',
    # ],
    'flip': [
        'm_down, 15',
        'm_down, 0',
        'L_f1, 15, R_f1, 15, L_f2, 15, R_f2, 15',
        'L_up, 15, R_up, 15',
        'm_ext, 15'
    ],
    'zero': [
        """f_f1, 0, f_f2, 0, f_up, 0, f_down, 0, f_ext, 0, 
        m_up, 0, m_down, 0, m_ext, 0, 
        L_f1, 0, L_f2, 0, L_up, 0, L_down, 0, L_ext, 0, 
        R_f1, 0, R_f2, 0, R_up, 0, R_down, 0, R_ext, 0
        """
    ],
    'test': [
        'm_up, 0, m_down, 0, m_ext, 15,3',
        'm_up, 15, m_down, 0, m_ext, 15,3',
        'm_up, 0, m_down, 15, m_ext, 15,3',
        'm_up, 15, m_down, 0, m_ext, 0,3',
        'm_up, 0, m_down, 15, m_ext, 0,3',
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
