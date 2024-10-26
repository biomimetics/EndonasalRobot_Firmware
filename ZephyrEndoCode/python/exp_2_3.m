result_name = 'exp_2_3_20240428_16-54-40_1200s_30s';
result_folder = fullfile('./data-raw', result_name, 'processed');
angle = readmatrix(fullfile(result_folder, 'mat_angle.csv'));
t = readmatrix(fullfile(result_folder, 'mat_t.csv'));
angle = angle(3:1:end);
% angle = angle - min(angle) + 10;
%angle = angle(1:1:500);
% angle = angle * -1;
% angle = angle - min(angle);
% angle = angle / max(angle);
%angle = [angle(1);angle];
%angle = [angle(1); angle(1:100); angle(100:60:end)];
%input = zeros(size(angle));
input = 0:1:6000;
input = input(1:1:end-3);
input = input.';

timeVector = 0:0.2:1200;
timeVector = timeVector(1:1:end-3);

inputSeries = input;
outputSeries = angle;
% Convert input and output data to iddata objects
Ts = 0.2;
data = iddata(outputSeries, inputSeries, Ts); % Ts is the sampling time


for nx=1:2

    
    % Estimate state-space model using n4sid
    opt = n4sidOptions('N4Horizon',[15 39 39]);
    
    sys = ssest(data, nx,'Ts', 0, 'DisturbanceModel','none',opt); % 4 is the desired order of the state-space model
    
    % sys = ssest(data, 2);
    
    simOutput = compare(data,sys);
    
    display(sys.Report.Fit);
    P = pole(sys);
    display(P);
    
    
    % simOutput = lsim(sys, inputSeries, inputSeries,sys.x0);
    % 
    % % Compare the simulated output with the actual output data
    actualOutput = outputSeries; % Assuming outputSeries is a timeseries object
    squaredErrors = (simOutput.OutputData - actualOutput).^2;
    
    % Calculate the Mean Squared Error (MSE)
    mse = mean(squaredErrors);
    % 
    
    % Plot data in log-log scale
    plot(input, simOutput.OutputData,'-', 'Color', 'blue'); % 'o' specifies the marker style (optional)
    hold on; % Hold the plot
    plot(input, actualOutput, '-', 'Color', 'red');
    
    writematrix(input, fullfile(result_folder, sprintf('mat-input-nx%d.csv',nx)),'Delimiter', ',')
    writematrix(simOutput.OutputData, fullfile(result_folder, sprintf('mat-simOutput-nx%d.csv',nx)),'Delimiter', ',')
    writematrix(actualOutput, fullfile(result_folder, sprintf('mat-actualOutput-nx%d.csv',nx)),'Delimiter', ',');
    xlabel('A');
    ylabel('B');
    hold off;
end