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


Check Franka Communication.
Check communication with franka. Must know franka ip address.
```ping 10.31.82.199```  
```communication_test 10.31.82.199```  
Check Franka python SDK Communication.  
May exchange with  ```franka_print_position.py``` with ```franka_move_gripper.py```
```python3 franka_print_position.py --ip 10.31.82.199```

Check Franka Communication via Ros 2.  

Process: 1. launch file 2. run controller 3. run script 4. read data


Check with no hardware.  
```ros2 launch franka_bringup franka.launch.py robot_type:=fr3 use_fake_hardware:=true load_gripper:=true```


Check with real hardware.  
Check launch files.  
```ls /opt/ros2_ws/src/franka_ros2/franka_bringup/launch```  
Check arguments of the launch file.  
```ros2 launch franka_bringup franka.launch.py --show-args```

List the controllers available.  
```ros2 control list_controllers```  
```ros2 topic list```  
```ros2 action list```  

List the hardware exposed.  
```ros2 control list_hardware_interfaces```  

If needed, copy the existing controller configuration to edit the controller.yaml (add or modify or remove a controller).  If the controller is modified, must always refer to the modified file as the default file will revert on Docker Container rebuild.
```cp /opt/ros2_ws/install/franka_bringup/share/franka_bringup/config/controllers.yaml ~/ros2_ws/controllers.yaml```  
```cat ~/ros2_ws/controllers.yaml```

Run the launch file to access hardware. May list the controllers.yaml file located in the src folder instead of the default franka_bringup location by specifying the controllers.yaml location.  
ros2 launch franka_bringup <your_launch_file>.launch.py robot_ip:=<ROBOT_IP>  
```ros2 launch franka_bringup franka.launch.py robot_type:=fr3 robot_ip:=10.31.82.199 load_gripper:=true controllers_yaml:=/home/sydney/ros2_ws/src/controllers.yaml```  



In a new terminal run a controller listed in controllers.yaml. This loads the arm controller (the launch doesn't do this).  
ros2 run controller_manager spawner <Controller_Name>  
```ros2 run controller_manager spawner joint_position_example_controller```  
In a new terminal, read data.
```ros2 topic echo /franka_robot_state_broadcaster/current_pose --once```  
```ros2 topic echo /joint_states --once```


Hone the gripper.  
```ros2 action send_goal /franka_gripper/homing franka_msgs/action/Homing "{}"```

In a new terminal run the franka_ros_client.py. fr3_arm_controller must be active to use franka_ros_client.py.  
Read joint states.    
```python3 franka_ros_client.py --echo```  
Joint 1 +0.1 rad (about 6°), over the default 10 seconds  
```python franka_ros_client.py --arm 0.1,0,0,0,0,0,0 --delta```  
Joint 7 move, slower (20 seconds)  
```python franka_ros_client.py --arm 0,0,0,0,0,0,0.1 --delta --duration 20```

If the first number is negative, use arm=  
Joint 7 -0.1 rad  
```python franka_ros_client.py --arm=0,0,0,0,0,0,-0.1 --delta```

All 7 values are target joints within 0.3 radian of the current position. This limit is for safety precautions. Use ```--allow-large``` tag to move over 3 radian.  
```python franka_ros_client.py --arm 0.0276,0.30,-0.001,-1.576,-0.057,1.837,0.892```

Grasp an object about 3 cm wide, gently. Defaults: width 0.005 m, speed 0.1 m/s, force 60 N.  
```python franka_ros_client.py --grasp --width 0.03 --speed 0.05 --force 20```



```python franka_ros_client.py --arm 0,0,0,0,0,0,0.1 --delta \
  --traj-topic /my_controller/joint_trajectory \
  --state-topic /franka/joint_states```


Must deactive the controller since only once controller can be used at a time.  
```ros2 control switch_controllers --deactivate joint_position_example_controller```  