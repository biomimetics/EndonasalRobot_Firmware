import cv2
import cv2.aruco as aruco
import numpy as np
import time
import os
class ArucoDetector:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        self.parameters = aruco.DetectorParameters()
        self.detector=aruco.ArucoDetector(self.dictionary, self.parameters)
        self.output_vid_flag = False
        
        while True:
            if isinstance(self.camera_id, (int,)):
                self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(self.camera_id)

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            _, frame = self.cap.read()
            print('frame size', frame.shape)
            assert frame.shape[0] == 1080 and frame.shape[1] == 1920
    
            # assert len(self.detector.detectMarkers(frame)[0]) > 0
            if np.all(frame == 0):
                self.cap.release()
                print('ERROR GETTING BLACK IMAGE')
            else:
                # cv2.imshow("Image", frame)

                break
        
        # while (True):
        #     _, frame = self.cap.read()
        #     cv2.imshow("Image", frame)
        #     key = cv2.waitKey(1)
        #     if key == ord('q'):
        #         break
        if not self.cap.isOpened():
            print("Unable to open the camera.")
            # exit()

    def start_video(self, output_dir):
        self.output_dir = output_dir
        self.output_vid_flag = True
        self.vid_save_count = 0
        self.fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.output_video = cv2.VideoWriter(os.path.join(self.output_dir, f'output_video_{self.vid_save_count}.avi'), self.fourcc, 5, (1920, 1080))
            
    def detect_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        corners, ids, _ = self.detector.detectMarkers(frame)
        # aruco.drawDetectedMarkers(frame, corners, ids)
        if self.output_vid_flag:
            self.output_video.write(frame)
        return corners, ids

    # def save_and_refresh_vid(self):
        # self.output_video.release()
        # self.vid_save_count += 1
        # self.output_video = cv2.VideoWriter(os.path.join(self.output_dir, f'output_video_{self.vid_save_count}.avi'), self.fourcc, 5, (1920, 1080))

    def terminate(self):
        self.cap.release()
        self.output_video.release()
        
    @staticmethod
    def corners_ids_proc(corners, ids, add_dict=None):
        corners = np.array(corners)[:, 0, :]
        ids = ids[:, 0]  
        corners_by_id = {}
        for i in range(len(ids)):
            corners_by_id[ids[i]] = corners[i]
            
        id_dict = {}
        for id in ids:
            cur_corners = corners_by_id[id]
            id_dict[id] = {
                'corners': cur_corners,
                'corners_center': np.mean(cur_corners, axis=0),
                'corners_len': np.linalg.norm(cur_corners[0]-cur_corners[1])
            }
            if not (add_dict is None):
                id_dict[id].update(add_dict)
        return id_dict
    def detect_frame_proc(self):
        for _ in range(2):
            corners, ids = self.detect_frame()
        if len(corners) == 0:
            return {}
                
        return self.corners_ids_proc(corners, ids)

if __name__ == '__main__':
    aruco_detector = ArucoDetector(0)
    aruco_detector.start_video('./')
    for _ in range(100):
        aruco_detector.detect_frame()
    aruco_detector.terminate()
# # Define the dictionary and parameters for ArUco detection
# dictionary = aruco.getPredefinedDictionary(aruco.DICT_6X6_250)
# parameters = aruco.DetectorParameters_create()

# # Define the initial position and orientation of the ArUco tag
# initial_pos = None
# initial_ori = None

# # Open the video capture device
# cap = cv2.VideoCapture(0)

# while True:
#     # Read a frame from the video stream
#     ret, frame = cap.read()

#     if ret:
#         # Detect the ArUco markers in the frame
#         corners, ids, _ = aruco.detectMarkers(frame, dictionary, parameters=parameters)

#         # If an ArUco marker is detected, compute the pose of the marker
#         if ids is not None:
#             rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, 0.05, camera_matrix, distortion_coefficients)
#             rvec, tvec = rvecs[0], tvecs[0]

#             # If this is the first frame, set the initial position and orientation of the marker
#             if initial_pos is None:
#                 initial_pos = tvec
#                 initial_ori = rvec
#             else:
#                 # Compute the distance and orientation change of the marker compared to the initial frame
#                 pos_change = np.linalg.norm(tvec - initial_pos)
#                 ori_change = np.linalg.norm(rvec - initial_ori)

#                 # Output the distance and orientation change
#                 print("Distance change: ", pos_change)
#                 print("Orientation change: ", ori_change)

#         # Draw the detected markers on the frame
#         frame_markers = aruco.drawDetectedMarkers(frame, corners, ids)

#         # Show the frame with the detected markers
#         cv2.imshow("Frame with detected ArUco markers", frame_markers)

#         # Wait for a key press and exit if the key is 'q'
#         if cv2.waitKey(1) & 0xFF == ord('q'):
#             break

# # Release the video capture device and close all windows
# cap.release()
# cv2.destroyAllWindows()