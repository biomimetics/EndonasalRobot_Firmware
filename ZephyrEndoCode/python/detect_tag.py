import cv2
import cv2.aruco as aruco
import numpy as np
from utils_data_process import cmp_corners
def detect_aruco_tag(frame):
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    # dictionary = aruco.extendDictionary(30, 3)

    # dictionary = aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
    parameters =  aruco.DetectorParameters()
    # parameters.polygonalApproxAccuracyRate=0.05
    detector = aruco.ArucoDetector(dictionary, parameters)
    return detector.detectMarkers(frame)

# Define the ID of the USB camera
camera_id = 0
import utils_aruco
utils_aruco.ArucoDetector(camera_id)
# Create a VideoCapture object to capture images from the camera
cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)                       
                       # Check if the camera is opened successfully
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

if not cap.isOpened():
    print("Unable to open the camera.")
    exit()
#print('hi')
init_corners=None

# j2_corners_center_img = cv2.imread('../pressure_artag_v1/runs/May23_16-52-19_2dcontrol_reachable_2d/vis/j2_corners_center.png', cv2.IMREAD_UNCHANGED)
while(True):
    # Capture an image from the camera
    ret, frame = cap.read()
    # print(frame.dtype, frame.shape)
    # Check if the image is captured successfully
    if not ret:
        print("Failed to capture the image.")
        exit()
        
    corners, ids, c = detect_aruco_tag(frame)
    aruco.drawDetectedMarkers(frame, corners, ids)

    if len(corners) > 0:
        corners = np.array(corners)[:, 0, :]
        ids = np.array(ids)[:, 0]
        corners_by_id = {}
        for j, tmp_id in enumerate(ids):
            corners_by_id[tmp_id] = corners[j]
        if 1 in corners_by_id and 3 in corners_by_id:
            print(cmp_corners(corners_by_id[1], corners_by_id[3])['rot'])
    # if len(corners) > 1:
    #     #print('hi')
    #     #print(np.shape(corners[0]))
    #     # print("hey this is corners1")a
    #     print(corners[1], ids[:, 0])
    # if ids is not None:
    #     for i in range(len(ids)):
    #         print(f"id: {ids[i][0]}; {corners[i][0][0]}, {corners[i][0][1]}, {corners[i][0][2]}, {corners[i][0][3]}")
        #print(ids[:, 0])
    # if ids is not None:
    #     for i, corner in enumerate(corners):
    #         x_min, y_min = corner.min(axis=1)[0]
    #         x_max, y_max = corner.max(axis=1)[0]
    #         print(x_min, y_min, x_max, y_max)
    #         cv2.rectangle(frame, (int(x_min), int(y_min)), (int(x_max), int(y_max)), (0, 255, 0), 2)

    # rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, 0.05, cpamera_matrix, distortion_coefficients)

    # if ids is not None:
    #     for i in range(len(ids)):
    #         aruco.drawAxis(img, camera_matrix, distortion_coefficients, rvecs[i], tvecs[i], 0.1)

    # Display the captured image
    # print(frame)
    cv2.imshow("Image", frame)
    
    # Wait for a key press
    key = cv2.waitKey(1)

    # Exit the loop if the "q" key is pressed
    if key == ord("q"):
        break

# Release the VideoCapture object and close all windows
cap.release()
cv2.destroyAllWindows()