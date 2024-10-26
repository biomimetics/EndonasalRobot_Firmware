import pickle
import numpy as np
import matplotlib.pyplot as plt
import os


pickle_file_path = "\queue.pickle"

def trim_effective(*args):
    start_times = [time[0] for _, time in zip(*[iter(args)]*2)]
    end_times = [time[-1] for _, time in zip(*[iter(args)]*2)]
    global_start_time = max(start_times)
    global_end_time = min(end_times)

    # Check for overlap
    if global_start_time > global_end_time:
        raise ValueError("No overlapping time period across datasets.")

    trimmed_data = []

    for value, time in zip(*[iter(args)]*2):
        # Find the indices for trimming
        start_idx = (np.abs(time - global_start_time)).argmin()
        end_idx = (np.abs(time - global_end_time)).argmin()
        
        # Trim the data arrays based on the indices
        value_trimmed = value[start_idx:end_idx+1]
        time_trimmed = time[start_idx:end_idx+1]

        trimmed_data.extend([value_trimmed, time_trimmed])

    return trimmed_data


def plot_centroids_with_gradient(centroids, time, x_label="X-axis(mm)", y_label="Y-axis(mm)", title="Centroids Over Time"):
    x, y = centroids[:, 0], centroids[:, 1]
    plt.figure(figsize=(10, 6))
    sc = plt.scatter(x, y, c=time, cmap='viridis', marker='o')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.colorbar(sc, label = 'time(s)')
    plt.grid(True)
    plt.axis('equal')
    plt.tight_layout()
    plt.show()

def plot_sensors(x, x_time, y, y_time, x_label="Input Value(PSI)", y_label="Output Value(PSI)", title="Graph"):
    plt.figure(figsize=(10,6))
    plt.plot(x, y, marker='o', linestyle='-', markersize = 1)
    plt.plot([min(x), max(x)], [min(x), max(x)], 'r--')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def simplePlot2(x, y, z, x_label="X-axis", y_label="Y-axis", title="Graph"):
    plt.figure(figsize=(10,6))
    #plt.plot(x, y, marker='o', linestyle='-')
    plt.scatter(x,y,s=10)
    plt.scatter(x,z,s=10)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def simplePlot(x, y, x_label="X-axis", y_label="Y-axis", title="Graph"):
    plt.figure(figsize=(10,6))
    #plt.plot(x, y, marker='o', linestyle='-')
    plt.scatter(x,y)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def simpleGradient(x, y, color, x_label="X-axis", y_label="Y-axis", c_label='Color', title="Graph"):
    plt.figure(figsize=(10,6))
    #plt.plot(x, y, marker='o', linestyle='-')
    sc = plt.scatter(x, y, c=color, cmap='Blues')
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.colorbar(sc, label = c_label)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def interpolate_centroids(centroids, times, interval=0.1):
    # Determine the start and end times for interpolation
    start_time = np.ceil(times[0])
    end_time = np.floor(times[-1])
    
    # Generate new times at which values need to be interpolated
    interpolated_times = np.arange(start_time, end_time + interval, interval)
    
    # Separate the x and y coordinates
    x_coords = centroids[:, 0]
    y_coords = centroids[:, 1]
    
    # Perform linear interpolation for x and y separately
    interpolated_x = np.interp(interpolated_times, times, x_coords)
    interpolated_y = np.interp(interpolated_times, times, y_coords)
    
    # Stack them together to form the interpolated centroids
    interpolated_centroids = np.stack((interpolated_x, interpolated_y), axis=-1)
    
    return interpolated_centroids, interpolated_times

def interpolate_sensors(values, times, interval=0.1):
    # Determine the start and end times for interpolation
    start_time = np.ceil(times[0])
    end_time = np.floor(times[-1])
    
    # Generate new times at which values need to be interpolated
    interpolated_times = np.arange(start_time, end_time + interval, interval)
    
    # Perform linear interpolation
    interpolated_values = np.interp(interpolated_times, times, values)
    
    return interpolated_values, interpolated_times

def find_centroid(coords):
    sum_x = sum(coord[0] for coord in coords)
    sum_y = sum(coord[1] for coord in coords)
    centroid_pixel = (sum_x / len(coords), sum_y / len(coords))

    # Find the average side length of the ArUco marker in pixels
    # Calculate the length of each side and then take the average
    side_lengths = [np.linalg.norm(coords[i] - coords[(i+1)%4]) for i in range(4)]
    avg_side_length_pixel = np.mean(side_lengths)

    # Compute the scale: pixels per millimeter
    aruco_real_world_size_mm = 5
    scale = avg_side_length_pixel / aruco_real_world_size_mm

    # Convert the centroid from pixels to millimeters
    return ([centroid_pixel[0] / scale, centroid_pixel[1] / scale])


def calculate_displacement(base, base_t, joint, joint_t):
    dx = base[:, 0] - joint[:, 0]
    dy = base[:, 1] - joint[:, 1]
    
    # Calculate the Euclidean distances
    distances = np.sqrt(dx**2 + dy**2)
    distances = distances - distances[0]
    return distances, base_t

with open(pickle_file_path, "rb") as f:
    data = pickle.load(f)

# Create dictionaries to store values and times for each device-ID combination
    values_dict = {}
    times_dict = {}

# Iterate through the data
    for entry in data:
        device, device_id, value, time = entry

        # If the device is a camera, compute the centroid
        if device == "camera":
            centroid = find_centroid(value[0][:, :, :2].reshape(-1, 2))
            value = centroid

        # Store the values and times in the respective dictionaries
        key = f"{device}_{device_id}"
        if key not in values_dict:
            values_dict[key] = []
            times_dict[key] = []
        values_dict[key].append(value)
        times_dict[key].append(time)

    # Convert lists to numpy arrays for easier processing
    for key in values_dict:
        values_dict[key] = np.array(values_dict[key])
        times_dict[key] = np.array(times_dict[key])

    # Accessing data for specific devices
    sensor_1_values = values_dict["sensor_sensor1"]
    sensor_1_times = times_dict["sensor_sensor1"]

    regulator_PWM1_values = values_dict["regulator_PWM1"]
    regulator_PWM1_times = times_dict["regulator_PWM1"]

    camera_1_centroids = values_dict["camera_4"]
    camera_1_time = times_dict["camera_4"]

    camera_base_centroids = values_dict["camera_0"]
    camera_base_time = times_dict["camera_0"]
    
    simplePlot(sensor_1_times, sensor_1_values)
    simplePlot(regulator_PWM1_times, regulator_PWM1_values)

    #Perform linear interpolation of data to get value at constant time interval
    sensor_1_values_itp, sensor_1_times_itp     = interpolate_sensors(sensor_1_values, sensor_1_times)
    regulator_PWM1_values_itp, regulator_PWM1_times_itp = interpolate_sensors(regulator_PWM1_values, regulator_PWM1_times)
    camera_1_centroids_itp, camera_1_time_itp           = interpolate_centroids(camera_1_centroids, camera_1_time)
    camera_base_centroids_itp, camera_base_time_itp     = interpolate_centroids(camera_base_centroids, camera_base_time)

    #Trim everything to have the same effective time range
    (
        sensor1_value_trimed, sensor1_time_trimed,
        regulator1_value_trimed, regulator1_time_trimed,
        camera_1_centroids_trimed, camera_1_time_trimed,
        camera_base_centroids_trimed, camera_base_time_trimed
    ) = trim_effective(
        sensor_1_values_itp, sensor_1_times_itp,
        regulator_PWM1_values_itp, regulator_PWM1_times_itp,
        camera_1_centroids_itp, camera_1_time_itp,
        camera_base_centroids_itp, camera_base_time_itp
    )

    # plot_sensors(regulator1_value_trimed, regulator1_time_trimed, sensor1_value_trimed, sensor1_time_trimed, 'Input Pressure(PSI)', 'Output Pressure(PSI)')

    # displacement, displacement_time = calculate_displacement(camera_base_centroids_trimed, camera_base_time_trimed, camera_1_centroids_trimed, camera_1_time_trimed)
    
    simplePlot(camera_1_time_trimed, camera_1_centroids_trimed[:, 0])

    # simpleGradient(displacement,sensor1_value_trimed,displacement_time,'displacement(mm)','pressure(PSI)','time')

    # simpleGradient(regulator1_value_trimed, sensor1_value_trimed, sensor1_time_trimed, 'time', 'Error(Input-Output)', 'output pressure(PSI)')

    # plot_centroids_with_gradient(camera_1_centroids_trimed, camera_1_time_trimed)

    # simplePlot2(sensor1_time_trimed,regulator1_value_trimed,sensor1_value_trimed,'time','pressure')
    # simplePlot(sensor1_time_trimed,sensor1_value_trimed)
