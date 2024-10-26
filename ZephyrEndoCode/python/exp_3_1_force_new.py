

import time
from run_stm_12 import *

def control_loop(q_output, result_folder): 
    global charStart
    i = 0
    regulator_vals = np.zeros(N_REGULATOR)
    state = StateStruct()
    print('control_loop- waiting for STM32READY (release RESET)\n')
    time.sleep(1)    # check periodically for start    
    while controlStop.is_set():
        time.sleep(1)    # check periodically for start 
    PRNWAIT = 20
    makeCmd('PRNWAIT', PRNWAIT)   # set wait time for state update in ms
    print('control_loop: started thread')
    time.sleep(3)
      #Initialize Pressure Regulators
    backbone_pressure = 20
    regulator_vals[3] = backbone_pressure
    makePressureCmd(regulator_vals)
    # time.sleep(3)

    pattern_count = 0
    actuator_pattern = generate_pattern1(0, 25, 0.5)
    n_cycle = 10

    while not controlStop.is_set():
        if not stateQ.empty():
            state = stateQ.get()
            if charStart.is_set():
                dumpQ(q_output, 'force', 'omega', state.adc8, time.time() - t0)
                if (i % (1500/PRNWAIT)) == 0:
                    if pattern_count % len(actuator_pattern) == 0:
                        dumpQ(q_output, 'info', 'CYCLE_DONE', (pattern_count // len(actuator_pattern))-1, time.time()-t0)
                        if pattern_count // len(actuator_pattern) >= n_cycle:
                            break
                    regulator_vals[3] = backbone_pressure
                    regulator_vals[6] = actuator_pattern[pattern_count % len(actuator_pattern)]  # channel 6
                    pattern_count += 1
                    makePressureCmd(regulator_vals)
                    print('n', pattern_count / len(actuator_pattern), 't', time.time() - t0, 'regulator', regulator_vals)
                    for j, val in enumerate(regulator_vals):
                        dumpQ(q_output, 'regulator', 'PWM{}'.format(j+1), val, time.time()-t0)
                i += 1  
                # if ((i%100) == 0):
                    # print('step %d  stateQ size= %d' % (i,stateQ.qsize()))
            time.sleep(0.001)
        else:
#            print('stateQ empty')
            # print("waiting for characterization start")
            time.sleep(0.001)
    
    makePressureCmd(np.zeros(N_REGULATOR))  
    
    charStart.clear()
    q_output_list = []
    while not q_output.empty():
        q_output_list.append(q_output.get())

    with open(os.path.join(result_folder, "queue.pickle"), "wb") as f:
        pickle.dump(q_output_list, f)
    print('queue saved')
    controlStop.set() # stop program after done characterization

    print('control_loop: finished thread')
    rcvStop.set()
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
    assert is_camera_available
    if is_camera_available:
        print('starting video...')
        aruco_detector.start_video(result_folder)

    q_output = queue.Queue()
    try_main(control_loop, q_output, result_folder)