# docker_sjsu_fr3vla
Docker container is specifc for the SJSU robotics lab for Franka 3 research.  
Docker container is on Ubuntu 24.04 with Ros 2 jazzy.  
Docker container will automatically enter .venv when ran.


# Docker Commands  
All commands my require sudo if user is not in sudo access group.


Docker compose build and start the container using your compose configurations  
```docker compose up -d --build```  
If need to clear cache  
```docker compose build --no-cache```


Drop into the interactive shell to see your files and run scripts  
```docker compose exec -it ros2 bash```


Close and exit docker container  
```docker compose down```


View docker container information:  
```docker ps```


Enter running docker container in a new terminal  
```sudo docker exec -it <CONTAINER_ID> bash```


# Commands which may be needed to pass through host computer for hardware access:  
Pass through display to host computer  
```xhost +local:docker```


Access video  
```sudo chmod 666 /dev/video*```


Realhand Hardware Access (will have to be ran each time the hand is connected)
Bring down the interface to configure parameters cleanly  
```sudo ip link set can0 down```  
Set the interface to standard 1 Mbps (1000000) baud rate for robotic hands  
```sudo ip link set can0 type can bitrate 1000000```  
Bring the socket interface up  
```sudo ip link set can0 up```
Verify the ip link has been brought up. The output should include <NOARP, UP, LOWER_UP, ECHO>  
```ip link show can0```



# Hardware Access Check:  
Check Ros 2  
in one terminal   
in a new terminal  


Check Webcam Access  
```cd src```  
```python test_webcam.py```


Check Intel RealSense Access  
```whereis realsense-viewer```  
```realsense-viewer```


Check Intel Realsense Ros 2 Communication  
```ros2 pkg list | grep realsense```  
Test camera node with ros2 run  
```ros2 run realsense2_camera realsense2_camera_node --ros-args -p enable_color:=false -p spatial_filter.enable:=true -p temporal_filter.enable:=true```  
Test camera code from launch  
```ros2 launch realsense2_camera rs_launch.py depth_module.depth_profile:=1280x720x30 pointcloud.enable:=true```

Check Realhand Ros2 Communication. Change the model and side (right/lelft) if necessary.  
Launch with default internal rates.  
```ros2 launch realhand_ros2 hand.launch.py model:=L6 side:=right interface_name:=can0```  
Launch with specific the telemetry tuning.  
```ros2 launch realhand_ros2 hand.launch.py model:=L6 side:=right interface_name:=can0   poll_on_start:=true stream_on_start:=true stream_queue_size:=300   poll_intervals_json:='{"angle": 0.03333333333333333, "force_sensor": 0.06666666666666667, "torque": 0.2, "speed": 0.5, "acceleration": 0.5, "temperature": 1.0, "current": 0.5, "fault": 1.0}'```  
Open a new terminal in the same running container. Publish to change the hand position. Must be ran from src/.  
```python3 realhand_pub_position.py```  
Open a new terminal in the same running container. Subscribe to view the hand state.  
```python3 realhand_sub_all_state.py```