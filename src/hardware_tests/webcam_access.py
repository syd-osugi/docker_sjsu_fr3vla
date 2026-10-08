# Target a specific index python test_webcam.py 2, do not enter a number for it to automatically search for an active camera
# !/usr/bin/env python3
import cv2
import sys

def test_camera():
    # Check if the user specified a manual camera index in the command line args
    if len(sys.argv) > 1:
        try:
            target_indices = [int(sys.argv[1])]
            print(f"Targeting user-specified camera index: {target_indices[0]}")
        except ValueError:
            print("[-] ERROR: Camera index must be an integer. Example: python test_webcam.py 0")
            sys.exit(1)
    else:
        # Default behavior: Search indices 0 through 3 automatically
        print("No index specified. Searching for operational video hardware (0-3)...")
        target_indices = range(4)
    
    cam_index = None
    cap = None
    
    # Iterate through the allowed list of indices
    for i in target_indices:
        print(f"Attempting to open /dev/video{i}...")
        cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
        if cap.isOpened():
            # Force MJPEG compression codec and limit frame buffer lag
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cam_index = i
            break
        cap.release()

    if cam_index is None:
        print("[-] ERROR: Target webcam node(s) could not be opened.")
        sys.exit(1)

    print(f"[+] SUCCESS: Connected to webcam at /dev/video{cam_index}")
    
    # Read backend properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print(f"    Resolution: {int(width)}x{int(height)}")

    # --- VIDEO LOOP FOR LIVE STREAMING ---
    try:
        print("Starting video loop... Press 'q' on the window to exit.")
        while True:
            ret, frame = cap.read()
            
            if not ret or frame is None:
                continue 

            # Render frame or placeholder text if the driver feeds zeroed out bytes
            if frame.any():
                cv2.imshow(f"Webcam Stream (/dev/video{cam_index})", frame)
            else:
                cv2.putText(frame, "Waiting for stream data...", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow(f"Webcam Stream (/dev/video{cam_index})", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[+] Exiting stream loop cleanly.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    test_camera()
