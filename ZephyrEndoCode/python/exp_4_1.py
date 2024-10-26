import time
from run_stm import *

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
    time_per_step = 4
    pattern = np.array(
        [

            #top bottom pair turning
            [0, 0, 20, 25, 0, 25, 0, 0],
            [0, 0, 15, 25, 0, 25, 0, 0],
            [0, 0, 15, 0, 0, 25, 0, 0],
            [0, 0, 15, 0, 25, 25, 0, 0],
            [0, 0, 0, 0, 25, 25, 0, 0],
            [0, 0, 0, 25, 0, 25, 0, 0],
            
            #left right pair turning
            [0, 20, 0, 25, 0, 25, 0, 0],
            [0, 15, 0, 25, 0, 25, 0, 0],
            [0, 15, 0, 25, 0, 0, 0, 0],
            [0, 15, 0, 25, 0, 0, 25, 0],
            [0, 0, 0, 25, 0, 0, 25, 0],
            [0, 0, 0, 25, 0, 25, 0, 0],

        ]
    )*1.
    
    regulator_vals =  np.array([0, 0, 0, 25, 0, 25, 0, 0])*1.
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
                    for j, r_val in enumerate(pattern):
                        # print("setting actuator to " +str(actuator_pressure)+ " PSI)")
                        state = stateQ.get()
                        regulator_vals = r_val
                        print(f'step {j}', pattern)

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
    try_main(control_loop, q_output, result_folder)

