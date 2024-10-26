max_pressure = 20
pattern = []

# Loop through the range from 1 to start_value (inclusive)
for i in range(1, max_pressure + 1):
    # Append 0 and the current value to the pattern
    pattern.append(0)
    pattern.append(i)
pattern.append(0)

# Print the pattern
print(pattern)
