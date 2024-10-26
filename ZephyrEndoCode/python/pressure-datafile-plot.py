# July 10, 2022
# code for plotting data from ZephyrSampleCode pressure sensor


# Imports
import numpy as np
import os
import matplotlib.pyplot as plot
plot.close("all")   # try to close all open figs
#import sys
#print sys.path
#comment next line to have plot windows outside browser
#%matplotlib inline

height = 8
width = 9

# Insert filename here
#filename = '..\..\research\MRI-Robot\MRIRobotProject\ZephyrSampleCode\Data\data.txt'
filename = '..\Data\data.txt'
print(filename)
 
    
###########################


#
# Read in the file
f = open(filename)
lines = f.readlines()  # returns list of lines
f.close()

#data format:
# line 1:  date/time stamp
# line 2: time chan0 chan1 chan2 temp
columns = 12
rows = len(lines)-2
print(lines[0])
print(lines[1])
linesFilter = []   # remove comment lines
#for i in range(0,len(lines)-1):
for textLine in lines:
#    print(textLine)
    data = textLine.split(',')  # split on comma
#    print("index %d data=%s" % (i, data)) 
   # split first element on space delimiter to find #, which indicates a comment
    firstChar = data[0].split()
    if (firstChar[0] == '#'):
        continue
#        print(textLine)
    else :
        linesFilter.append(textLine)
        
        
 #      
rows=len(linesFilter)-2  # considering first two header lines 
print('rows=%s,columns=%s' %(rows, columns))
temp = "".join(linesFilter[2:]).replace('\n',',') # remove line feeds to make single comma separated string
temp1 = temp[:-1].split(',') # create array of strings for all elements 
temp2 = list(map(float,temp1)) # convert list of strings to list of floats
data = np.reshape(temp2,(rows,columns))

###################################
def getDatatFromFile(filename):
    # Read in the file
    f = open(filename)
    lines = f.readlines()  # returns list of lines
    f.close()
    linesFilter = []   # remove comment lines
    for textLine in lines:
        data = textLine.split(',')  # split on comma
        firstChar = data[0].split()
        if (firstChar[0] == '#'):
            continue
        else :
            linesFilter.append(textLine)
    rows=len(linesFilter)-2  # considering first two header lines 
    print('rows=%s,columns=%s' %(rows, columns))
    temp = "".join(linesFilter[2:]).replace('\n',',') # remove line feeds to make single comma separated string
    temp1 = temp[:-1].split(',') # create array of strings for all elements 
    temp2 = list(map(float,temp1)) # convert list of strings to list of floats
    data = np.reshape(temp2,(rows,columns)) 
    return data[:,0], data[:,4]  # gtime, pressure sensor
     
    
    
    
    
    
    
    
    
    

###################################

time=data[:,0]
chan0=data[:,4]  # pressure sensor
#chan1=data[:,2]
#chan2=data[:,3]


fig = plot.figure(figsize=(9,6))
plot.ylabel('pressure (A/D units)')
plot.xlabel('time (sec)')
legend_label=np.array(np.zeros(4), dtype=str) # initialize blank array for legend


# plot.legend(legend_label, loc='upper right', bbox_to_anchor=(.8, 0.8), ncol=1)
legend_label[0]='Chan 0'
#legend_label[1]='Chan 1'
#legend_label[2]='Chan 2'
#legend_label[3]='$\Delta$ Temperature'
# plot.plot(time[1:850],chan0[1:850],'-')
# time, chan = getDatatFromFile('data2.txt')
# plot.plot(time[1:850],chan[1:850],'-')

# time, chan = getDatatFromFile('data3.txt')
# plot.plot(time[1:850],chan[1:850],'-')

# time, chan = getDatatFromFile('data4.txt')
# plot.plot(time[1:850],chan[1:850],'-')

fileList = os.listdir('../Data')
legend_label = []
for name in fileList:
    if( name[0:4] == 'data'):
        fileName = '../Data/'+name
        print(fileName)
        time, chan = getDatatFromFile(fileName)
        plot.plot(time[1:],chan[1:],'-')
        legend_label.append(name)
        
#plot.plot(time,chan1*100,'-')
#plot.plot(time,chan2*100,'-')
#plot.plot(time,temperature,'-')
#plot.axis([7.5,36, 0, 2000])
plot.legend(legend_label, loc='upper right', fontsize=12)
#plot.legend(legend_label)
plot.grid()
plot.title('pressure regulator with 2.1 m tube')   






