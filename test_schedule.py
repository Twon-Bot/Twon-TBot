from datetime import datetime, timedelta

hours_ago = 24  # Simulate different inputs

pack_time = datetime.utcnow() - timedelta(hours=hours_ago)
print("Pack time (UTC):", pack_time)

if pack_time.hour < 6:  
    nearest_6pm = pack_time.replace(hour=18, minute=0, second=0, microsecond=0) - timedelta(days=1)
elif pack_time.hour < 18:  
    nearest_6pm = pack_time.replace(hour=18, minute=0, second=0, microsecond=0) - timedelta(days=1)
else:  
    nearest_6pm = pack_time.replace(hour=18, minute=0, second=0, microsecond=0)

print("Nearest 6 PM UTC:", nearest_6pm)

# Calculate timestamps
time1 = int((nearest_6pm + timedelta(days=1)).timestamp())
time2 = int((nearest_6pm + timedelta(days=1, hours=8)).timestamp())
time3 = int((nearest_6pm + timedelta(days=2, hours=8)).timestamp())
time4 = int((nearest_6pm + timedelta(days=2, hours=0)).timestamp())

print("Time1:", time1)
print("Time2:", time2)
print("Time3:", time3)
print("Time4:", time4)
