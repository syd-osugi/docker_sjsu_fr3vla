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

# Hardware Access Check
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