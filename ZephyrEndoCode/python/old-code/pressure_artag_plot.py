import sys
# setting path
sys.path.append('../utils_python')

import argparse
# import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pickle
import os
import utils_icp
import utils_aruco
from matplotlib.ticker import MaxNLocator

# j_id_dict = {0: 23, 1: 28, 2: 15}
# j_id_dict = {0: 23}
j_id_dict = {0: 1}
# j_id_dict = {0: 28}

def q_dict_add(q_dict, k, data, t):
	if not (k in q_dict):
		q_dict[k] = {
			'data': [],
			'time': []
		}
	q_dict[k]['data'].append(data)
	q_dict[k]['time'].append(t)
def q_list_to_dict(q_list):
	q_dict = {}
	for x in q_list:
		k = x[0]
		data = x[1:-1]
		t = x[-1]
		if k == 'arduino':
			data_list = data[0].split(',')
			for i in range(0, len(data_list), 2):
				k_add = data_list[i]
				val = data_list[i+1]
				try:
					val = float(val)
				except:
					pass
				# val = float(val) if val.isnumeric() else val
				q_dict_add(q_dict, k_add, val, t)
		else:
			q_dict_add(q_dict, k, data, t)
	
	return q_dict

def plt_scatter_gradient_color(ax, x, y, cmap):
	z = np.arange(len(x))
	cmap = plt.get_cmap(cmap)
	# Normalize the values to range from 0 to 1
	norm = plt.Normalize(z.min(), z.max())
	# Set up the colors as a gradient from lightest to darkest
	colors = cmap(norm(z))
	# Create the scatter plot with gradient colors
	ax.scatter(x, y, c=colors)
	# ax.colorbar()

def load_run(run_dir=None, normalizer_data=None, plot_corners=False, vis_dir=None):
	print('loading run', run_dir)
	with open(run_dir, "rb") as f:
		q_list = pickle.load(f)	
	q_dict = q_list_to_dict(q_list)
	aruco_side_len = []
	aruco_center_pos = []
	aruco_corners_init={}
	aruco_rel_pose_by_id = {}
	aruco_id_dict_arr = []

	from matplotlib.patches import Polygon
	if plot_corners:
		fig, ax = plt.subplots(1, 1, figsize=(1920/200., 1080/200.))
	for ii, data in enumerate(q_dict['aruco']['data']):
		corners = data[0][0]
		ids = data[0][1]
		aruco_id_dict = utils_aruco.ArucoDetector.corners_ids_proc(corners, ids)
		aruco_id_dict_arr.append(aruco_id_dict)

		if ii == 0:
			j0_ori_corners_len = aruco_id_dict_arr[0][j_id_dict[0]]['corners_len']
		rect = data[0][0][0][0]
		rect_center = np.mean(rect, axis=0)
		side_len = np.linalg.norm(rect[0]-rect[1])
		aruco_side_len.append(side_len)
		aruco_center_pos.append(rect_center)
		for cur_id in aruco_id_dict:
			if not (cur_id in aruco_corners_init):
				aruco_corners_init[cur_id]=aruco_id_dict[cur_id]['corners']
				aruco_rel_pose_by_id[cur_id] = {'time': [], 'angle': [], 't0': [], 't1': []}
			
			aruco_corners_init_centroid = np.mean(aruco_corners_init[cur_id], 0)
			pose_angle, pose_t = utils_icp.best_fit_transform_2d(aruco_corners_init[cur_id]-aruco_corners_init_centroid, aruco_id_dict[cur_id]['corners']-aruco_corners_init_centroid)
			# pose_t=np.mean(corners[i], 0)-np.mean(aruco_corners_init[cur_id], 0)
			
			aruco_rel_pose_by_id[cur_id]['time'].append(q_dict['aruco']['time'][ii])
			aruco_rel_pose_by_id[cur_id]['angle'].append(pose_angle)
			aruco_rel_pose_by_id[cur_id]['t0'].append(pose_t[0] / j0_ori_corners_len * 0.5)
			aruco_rel_pose_by_id[cur_id]['t1'].append(pose_t[1] / j0_ori_corners_len * 0.5)

			if ii%50 == 0 and plot_corners:
				polygon_patch = Polygon(aruco_id_dict[cur_id]['corners'], closed=True, linewidth=1, edgecolor='r', facecolor='none')
				ax.add_patch(polygon_patch)
	print('j0_ori_corners_len', j0_ori_corners_len)
	if plot_corners:
		ax.set_xlim(0, 1920)
		ax.set_ylim(0, 1080)
		ax.set_aspect('equal', adjustable='box')
		plt.show()
	
	aruco_id_dict_all = {}
	for d in aruco_id_dict_arr:
		for k1, d1 in d.items():
			if not k1 in aruco_id_dict_all:
				aruco_id_dict_all[k1] = {}
			for k2, value in d1.items():
				if not k2 in aruco_id_dict_all[k1]:
					aruco_id_dict_all[k1][k2] = []
				aruco_id_dict_all[k1][k2].append(value)
	for k1 in aruco_id_dict_all:
		for k2 in aruco_id_dict_all[k1]:
			aruco_id_dict_all[k1][k2] = np.array(aruco_id_dict_all[k1][k2])

	aruco_side_len = np.array(aruco_side_len)
	aruco_center_pos = np.array(aruco_center_pos)
	if not (normalizer_data is None):
		aruco_center_pos_delta = aruco_center_pos - normalizer_data['aruco_center_pos'][0:1] 
		#aruco_center_pos_delta = aruco_center_pos_delta / normalizer_data['aruco_side_len'][0]
	else:
		aruco_center_pos_delta = aruco_center_pos - aruco_center_pos[0:1] 
		# aruco_center_pos_delta = aruco_center_pos_delta / aruco_side_len[0]

	if 'sensor11/reading' in q_dict:
		regulator1_input_time = q_dict['regulator1/write']['time']
		regulator1_input_val = np.array(q_dict['regulator1/write']['data'])
		print(np.shape(q_dict['sensor11/reading']['time']))
		print((q_dict['sensor11/reading']['data']))
		aruco_pressure_sensor11_interp = np.interp(q_dict['aruco']['time'], q_dict['sensor11/reading']['time'], q_dict['sensor11/reading']['data'])
		aruco_pressure_input1_interp = np.interp(q_dict['aruco']['time'], regulator1_input_time, regulator1_input_val)

	data_dict = {
		'aruco_center_pos': aruco_center_pos,
		'aruco_side_len': aruco_side_len,
		'aruco_center_pos_delta': aruco_center_pos_delta,
		'aruco_rel_pose_by_id': aruco_rel_pose_by_id,
		'aruco_id_dict': aruco_id_dict_all
	}
	print(list(q_dict.keys()))
	if 'sensor11/reading' in q_dict:
		print('hello')
		data_dict.update({
			'aruco_pressure_input1_interp': aruco_pressure_input1_interp,
			'aruco_pressure_sensor11_interp': aruco_pressure_sensor11_interp,
			'regulator1_input_time': regulator1_input_time,
			'regulator1_input_val': regulator1_input_val,
		})
	return q_dict, data_dict
if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--dir")
	parser.add_argument("--run_name")

	args = parser.parse_args()

	args.dir = os.path.join('./runs', args.run_name, 'output', 'queue.pickle')
	# args.dir = 'queue.pickle'
	vis_dir = os.path.join('./runs', args.run_name, 'vis')

	q_dict, data_dict = load_run(args.dir, plot_corners=True, vis_dir=vis_dir)

	# aruco_center_pos = data_dict['aruco_center_pos']
	# aruco_center_pos = np.array(aruco_center_pos)
	# print('center pos', aruco_center_pos[0:1])
	# aruco_center_pos_delta = aruco_center_pos - np.array([[945,513.5]]) #zero point for  Apr26_13-23-53_single-noload-10cycle



	# regulator_input_t = q_dict['regulator/analog_input']
	# regulator_input_y = 
	# print(q_dict['aruco']['data'][0])
	# print(q_dict.keys())

	fig, ax = plt.subplots(1, 1, figsize=(8, 8))
	# ax.scatter(q_dict['regulator/analog_input']['time'], np.array(q_dict['regulator/analog_input']['data'])/255*72.52, label='regulator_input')
	# ax.scatter(q_dict['sensor/reading']['time'], q_dict['sensor/reading']['data'], c='blue', label='pressure_sensor')
	# ax.yaxis.set_major_locator(MaxNLocator(nbins=10))

	ax2 = ax
	# ax2 = ax.twinx()
	# ax2.scatter(aruco_center_pos[:, 0], aruco_center_pos[:, 1])
	# ax2.scatter(aruco_center_pos[:50, 0], aruco_center_pos[:50, 1], c='red')

	# aruco position vs. time graph
	# ax2.scatter(q_dict['aruco']['time'], aruco_center_pos_delta[:, 0], c='red', label='aruco delta-0')
	# ax2.scatter(q_dict['aruco']['time'], aruco_center_pos_delta[:, 1], c='green', label='aruco delta-1')

	#aruco position vs. pressure graph
	print(np.shape(data_dict['aruco_pressure_sensor11_interp']))
	print(np.shape(data_dict['aruco_center_pos_delta']))
	ax2.scatter(data_dict['aruco_pressure_sensor11_interp'], data_dict['aruco_center_pos_delta'][:,0], c='red', label='pressure_sensor vs. pos-0')
	#plt_scatter_gradient_color(ax2, data_dict['aruco_pressure_sensor11_interp'], data_dict['aruco_center_pos_delta'][:, 1], cmap='Blues')
	# plt_scatter_gradient_color(ax2, data_dict['aruco_pressure_sensor11_interp'], data_dict['aruco_center_pos_delta'][:, 1], cmap='Blues')

	# ax2.scatter(aruco_pressure_input1_interp, aruco_center_pos_delta[:, 0], c='green', label='pressure_input vs. pos-0')
	# ax2.scatter(aruco_pressure_sensor11_interp, aruco_center_pos_delta[:, 1], c='red', label='pressure_sensor vs. pos-1')
	# ax2.scatter(aruco_pressure_input1_interp, aruco_center_pos_delta[:, 1], c='green', label='pressure_input vs. pos-1')

	# plt_scatter_gradient_color(ax2, data_dict['aruco_rel_pose_by_id'][28]['time'], data_dict['aruco_rel_pose_by_id'][28]['angle'], cmap='Blues')
	# plt_scatter_gradient_color(ax2, data_dict['aruco_rel_pose_by_id'][15]['t0'], data_dict['aruco_rel_pose_by_id'][15]['t1'], cmap='Blues')

	# ax2.set_ylim([-0.1, 1])
	# ax2.set_ylim([-3, 0.1])
	# ax2.set_aspect('equal', adjustable='box')

	# plt.show()
	j0_corners_center = data_dict['aruco_id_dict'][j_id_dict[0]]['corners_center']
	j0_corners_len = data_dict['aruco_id_dict'][j_id_dict[0]]['corners_len']
	# j0_corners_center_disp_normalized = np.linalg.norm(j0_corners_center - j0_corners_center[0:1], axis=-1) / j0_corners_len * 0.5 / 2.2*0.9
	# j0_corners_center_disp_normalized = np.linalg.norm(j0_corners_center - j0_corners_center[0:1], axis=-1) / j0_corners_len * 0.5 / 2.1*0.8
	j0_corners_center_disp_normalized = np.linalg.norm(j0_corners_center - j0_corners_center[0:1], axis=-1) / j0_corners_len * 0.5 / 2.1*0.8
	# j0_corners_center_disp_normalized = np.linalg.norm(j0_corners_center - j0_corners_center[0:1], axis=-1) / j0_corners_len * 0.62 / 2.8*0.5

	aruco_time = data_dict['aruco_rel_pose_by_id'][j_id_dict[0]]['time']
	# j0_corners_center_disp_normalized = (j0_corners_center - j0_corners_center[0:1])[:, 0] 
	j0_corners_center_disp_normalized = np.linalg.norm(j0_corners_center - j0_corners_center[0:1] , axis=-1) 
	# j0_corners_center_disp_normalized = j0_corners_center[:, 0] 
	

	j0_pressure_sensor_interp = data_dict['aruco_pressure_sensor11_interp']
	print('data len', j0_pressure_sensor_interp.shape)


	#plt_scatter_gradient_color(ax, aruco_time, j0_corners_center_disp_normalized, cmap='Blues')
	#ax.scatter(q_dict['sensor11/reading']['time'], q_dict['sensor11/reading']['data'])
	#ax.scatter(q_dict['sensor11/reading']['time'], q_dict['sensor11/reading']['data'])
	
	ax.legend(loc='upper left')
	ax2.legend(loc='upper right')

	fig.tight_layout()

	with open(os.path.join(vis_dir, "data_dict.pickle"), "wb") as f:
			pickle.dump(data_dict, f)

	plt.show()
	# for j_id in j_id_dict:
	# 	# plot joint position
	# 	fig, ax = plt.subplots(1, 1, figsize=(19.2, 10.94))

	# 	# plt_scatter_gradient_color(ax, data_dict['aruco_id_dict'][j_id_dict[j_id]]['corners_center'][:, 0], data_dict['aruco_id_dict'][j_id_dict[j_id]]['corners_center'][:, 1], cmap='Blues')
	# 	# ax.scatter(data_dict['aruco_id_dict'][j_id_dict[j_id]]['corners_center'][:, 0], data_dict['aruco_id_dict'][j_id_dict[j_id]]['corners_center'][:, 1], c='r')
	# 	ax.set_xlim(0, 1920)
	# 	ax.set_ylim(0, 1080)
	# 	ax.axis('off')
	# 	# Save the figure without axes and surrounding whitespace
	# 	fig.tight_layout()
	# 	fig.savefig(os.path.join(vis_dir, f'j{j_id}_corners_center.png'), bbox_inches='tight', pad_inches=0, dpi=101.59)
	# 	# ax.set_aspect('equal', adjustable='box')
	# 	plt.show()