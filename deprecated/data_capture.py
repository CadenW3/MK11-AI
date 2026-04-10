import mss
import cv2
import numpy as np
import time
import os

# Create a folder for your training images
os.makedirs("dataset/images", exist_ok=True)

sct = mss.mss()
# Adjust this to match your MK11 resolution/monitor
monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}

print("Starting capture in 5 seconds. Open MK11 and enter a match!")
time.sleep(5)

count = 0
try:
    while count < 500:
        # Capture the screen
        img = np.array(sct.grab(monitor))
        # Convert from BGRA to BGR for OpenCV
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # Save the image
        file_path = f"dataset/images/frame_{count}.jpg"
        cv2.imwrite(file_path, frame)
        
        print(f"Captured {count}/500")
        count += 1
        
        # Wait 2 seconds between captures
        time.sleep(2)
        
except KeyboardInterrupt:
    print("Capture stopped.")

print(f"Done! 500 images saved to dataset/images/")