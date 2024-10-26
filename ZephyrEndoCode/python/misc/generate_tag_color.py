import cv2
import cv2.aruco as aruco
import numpy as np

# Define the size and ID of the ArUco tag
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
# aruco_dict = aruco.extendDictionary(30, 3)
tag_size = 400
# tag_id_arr = [0, 1, 2, 3, 4, 5, 14, 20, 21, 22, 23, 24, 25]
tag_id_arr = list(range(11))

# Generate the ArUco tag image
for tag_id in tag_id_arr:
    red_background = np.zeros((tag_size, tag_size, 3), dtype=np.uint8)
    # red_background[:, :] = [0, 0, 255]  # red tag
    red_background[:, :] = [0, 0, 0]  # black tag
    tag_image = np.zeros((tag_size, tag_size), dtype=np.uint8)
    tag_generator = aruco_dict.generateImageMarker(tag_id, tag_size, tag_image, 1)
    print(tag_generator)

    for i in range(tag_size):
        for j in range(tag_size):
            if tag_image[i][j] == 255:
                red_background[i][j] = np.array([255, 255, 255])
    # Save the generated image
    cv2.imwrite('tags/aruco_tag_{}.png'.format(tag_id), red_background)

    