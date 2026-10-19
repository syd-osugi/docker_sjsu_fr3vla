# docker_sjsu_fr3vla
Docker container is specifc for the SJSU robotics lab for Franka 3 research.  
Docker container is on Ubuntu 24.04 with Ros 2 jazzy.  
Docker container will automatically enter .venv when ran.


# General Docker Commands  
All commands my require sudo if user is not in sudo access group.


1. Docker compose build and start the container using your compose configurations  
```docker compose up -d --build```  
If need to clear cache, use ```--no-cache``` tag.    
```docker compose build --no-cache```


2. Drop into the interactive shell to see your files and run scripts.  
```docker compose exec -it ros2 bash```


3. Close and exit docker container  
```docker compose down```

## Open a second terminal within the same Docker Container
1. View docker container information.  
```docker ps```


2. Enter running docker container in a new terminal.  
```sudo docker exec -it <CONTAINER_ID> bash```


# Commands which may be needed to pass through host computer for hardware access:  
## Pass through display to host computer  
```xhost +local:docker```


## Access video  
```sudo chmod 666 /dev/video*```


## Realhand Hardware Access
Note: will have to be ran each time the hand is connected.  
1. Bring down the interface to configure parameters cleanly  
```sudo ip link set can0 down```  
2. Set the interface to standard 1 Mbps (1000000) baud rate for robotic hands  
```sudo ip link set can0 type can bitrate 1000000```  
3. Bring the socket interface up  
```sudo ip link set can0 up```
4. Verify the ip link has been brought up. The output should include <NOARP, UP, LOWER_UP, ECHO>  
```ip link show can0```

## Meta Quest Access
Create a adb-keys folder within root directory on the host.  
```mkdir -p adb-keys```  
Connect the headset to the PC via USB cable. A pop-up requesting USB debugging will be seen through the heatset. Allow debugging via USB.  
If no pop-up is seen, check whether the device is authorized.  
```abd devices```  
If the device is unauthorized, pass through key access. Run the following command on the host.
``` sudo chown -R 1000:1000 adb-keys```

Run on host to allow local processes to connect to the server.
```xhost +local:```  
Revert when finished  
```xhost -local:```

# Hardware Access Check:  
## Ros 2  
1. Start a talker node.  
```ros2 run demo_nodes_cpp talker```
2. Open a new terminal. Start a listener node.  
```ros2 run demo_nodes_cpp listener```


## Webcam  
1. ```cd src/hardware_tests```  
2. Execute py file to open the webcam and view the feed. Must pass through display access to the host.  
May target a specific index, python test_webcam.py 2, an empty index will automatically search for an active camera.  
```python test_webcam.py```


## Intel RealSense 
### Realsense-viewer
1. Verify realsense-viewer is installed.  
```whereis realsense-viewer```  
2. Open realsense-viewer to display RGB and depth passthrough.  
```realsense-viewer```


### Intel Realsense Ros 2 Communication  
1. Verify realsense exists within ros2 package list.  
```ros2 pkg list | grep realsense```  
2. Test camera node with ros2 run to start a single executable node. 
```ros2 run realsense2_camera realsense2_camera_node --ros-args -p enable_color:=false -p spatial_filter.enable:=true -p temporal_filter.enable:=true```  
3. Test camera code from launch.  
```ros2 launch realsense2_camera rs_launch.py depth_module.depth_profile:=1280x720x30 pointcloud.enable:=true```

## Realhand
### Realhand Python SDK
1. Gui???


### Realhand Ros2 Communication.
Change the model and side (right/lelft) if necessary.  

1. Launch with default internal rates.  
```ros2 launch realhand_ros2 hand.launch.py model:=L6 side:=right interface_name:=can0```  

    Or launch with specific telemetry tuning.  
```ros2 launch realhand_ros2 hand.launch.py model:=L6 side:=right interface_name:=can0   poll_on_start:=true stream_on_start:=true stream_queue_size:=300   poll_intervals_json:='{"angle": 0.03333333333333333, "force_sensor": 0.06666666666666667, "torque": 0.2, "speed": 0.5, "acceleration": 0.5, "temperature": 1.0, "current": 0.5, "fault": 1.0}'```  
3. Open a new terminal in the running Docker Container. Publish to change the hand position. Must be ran from src/hardware_tests.  
```python3 realhand_pub_position.py```  
4. Open a new terminal in the same running container. Subscribe to view the hand state.  
```python3 realhand_sub_all_state.py```


## Franka
Check communication with franka. Must know franka ip address.
```ping 10.31.82.199```  
```communication_test 10.31.82.199```  

## Franka Python SDK  
1. May exchange   ```franka_print_position.py``` with ```franka_move_gripper.py```  
```python3 franka_print_position.py --ip 10.31.82.199```

## Franka Ros 2 Communication 

Process: 1. launch file 2. run controller 3. run action 4. read data/topic 5. Deactivate controller

Send commands with action instead of topics. Actions use the controller to generate safe trajectories, whereas topics will instantly move the robot if an active real-time controller is listening. 

### Franka No hardware
1. Check with no hardware.  
```ros2 launch franka_bringup franka.launch.py robot_type:=fr3 use_fake_hardware:=true load_gripper:=true```


### Franka with hardware 
List the hardware exposed.  
```ros2 control list_hardware_interfaces``` 

#### 1. Launch File
1. View launch files available.    
```ls /opt/ros2_ws/src/franka_ros2/franka_bringup/launch```  
2. View arguments of a specific launch file.  
```ros2 launch franka_bringup franka.launch.py --show-args```
3. Run the launch file to access hardware. May list the controllers.yaml file located in the src folder instead of the default franka_bringup location by specifying the controllers.yaml location.  

    The command is of the form: ros2 launch franka_bringup <your_launch_file>.launch.py robot_ip:=<ROBOT_IP>  
```ros2 launch franka_bringup franka.launch.py robot_type:=fr3 robot_ip:=10.31.82.199 load_gripper:=true controllers_yaml:=/home/sydney/ros2_ws/src/controllers.yaml```  

#### 2. Controllers
1. List controllers available.  
```ros2 control list_controllers```  
2. If needed, copy the existing controller configuration to edit the controller.yaml (add or modify or remove a controller). If the controller is modified, must always refer to the modified file as the default file will revert on Docker Container rebuild.
```cp /opt/ros2_ws/install/franka_bringup/share/franka_bringup/config/controllers.yaml ~/ros2_ws/controllers.yaml```  
```cat ~/ros2_ws/controllers.yaml```
3. . In a new terminal (different from launch), run a controller. The launch doesn't load controllers.  

    The command is of the form: ros2 run controller_manager spawner <Controller_Name>  
```ros2 run controller_manager spawner joint_position_example_controller```  
4. To switch controllers, deactive the controller then start a new controller since only once controller can be used at a time.  
```ros2 control switch_controllers --deactivate joint_position_example_controller``` 

#### 3. Franka Action
1. View available actions.   
```ros2 action list``` 
2. View the parameter field names and data types for <goal_feedback_parameters_in_yaml>  
```ros2 action show franka_msgs/action/Grasp```
3. In a new, third terminal. Send commands in the form.  
ros2 action send_goal <action_name> <action_type> "<goal_feedback_parameters_in_yaml>" 
```ros2 action send_goal /franka_gripper/homing franka_msgs/action/Homing "{}"```
```ros2 action send_goal /franka_gripper/move franka_msgs/action/Move "{width: 0.04, speed: 0.1}"```

#### 4. Franka Topic
1. View topic list  
```ros2 topic list```  
2. In a fourth terminal, run the topic.  

    The command is in the form: ros2 topic <subcommand> <topic_name> <topic_type> <arguments>  

    Echo live data:  
```ros2 topic echo /franka_robot_state_broadcaster/current_pose --once```  
```ros2 topic echo /joint_states --once```

#### Franka Full Process
1. Terminal 1, Launch: 
```ros2 launch franka_bringup franka.launch.py robot_type:=fr3 robot_ip:=10.31.82.199 load_gripper:=true controllers_yaml:=/home/sydney/ros2_ws/src/controllers.yaml```
2. Terminal 2, Controller:  
fr3_arm_controller must be active to use franka_ros_client.py.  
```ros2 run controller_manager spawner fr3_arm_controller```
3. Terminal 4, run franka_ros_client.py.  

    Read joint states.    
```python3 franka_ros_client.py --echo```  

    Joint 1 +0.1 rad (about 6°), over the default 10 seconds.  
```python franka_ros_client.py --arm 0.1,0,0,0,0,0,0 --delta```  

    Joint 7 move, slower (20 seconds).  
```python franka_ros_client.py --arm 0,0,0,0,0,0,0.1 --delta --duration 20```

    If the first number is negative, use ```arm=```  
Joint 7 -0.1 rad.  
```python franka_ros_client.py --arm=0,0,0,0,0,0,-0.1 --delta```

    Move by a small delta.  
```python franka_ros_client.py --arm 0,0,0,0,0,0,0.1 --delta \```  
```  --action-server /fr3_arm_controller/follow_joint_trajectory \```  
```  --state-topic /joint_states```  

    All 7 values are target joints within 0.3 radian of the current position. This limit is for safety precautions. Use ```--allow-large``` tag to move over 3 radian.  
```python franka_ros_client.py --arm 0.0276,0.30,-0.001,-1.576,-0.057,1.837,0.892```

    Grasp an object about 3 cm wide, gently. Defaults: width 0.005 m, speed 0.1 m/s, force 60 N.  
```python franka_ros_client.py --grasp --width 0.03 --speed 0.05 --force 20```

4. Must deactive the controller since only once controller can be used at a time.  
```ros2 control switch_controllers --deactivate fr3_arm_controller```  

# VR Teleoperation
## Hand-Tracker-Streamer App
1. If there is any server running on the host, kill it. If an adb server is already running on the host, then the Docker Containers adb will connect to it through a shaired network.  
```adb kill-server```

2. Start docker container.  

3. Connect the headset to the PC via USB cable. A pop-up requesting USB debugging will be seen through the heatset. Allow debugging via USB.  
If no pop-up is seen, check whether the device is authorized.  
```adb devices```  
If the device is unauthorized, pass through key access. Run the following command on the host.
``` sudo chown -R 1000:1000 adb-keys```

4. Remaps the port number to the assigned port. 
The command is in the format: adb reverse tcp:<PORT> tcp:<PORT>  
```adb reverse tcp:8000 tcp:8000```  

5. Verify the active ports.  
```adb reverse --list```

6. Start the receiver.  
The command is in the format: python /opt/hand-tracking-streamer/scripts/visualizer.py --protocol tcp --host <HOST_IP> --port <PORT> --show-fingers  
```python /opt/hand-tracking-streamer/scripts/visualizer.py --protocol tcp --host 127.0.0.1 --port 8000 --show-fingers```

7. Within the VR app, change the protocol to tcp (wired), the host ip, and the port to match the command from step 6. 

## Franka-Vr-Teleop
1. View available launch files.  
```find /opt/ros2_ws/src/franka-vr-teleop -name "*.launch.py"```

2. Read the launch arguments for the UDP port and node. The vr_upd_port is the headset to the Ros2 node; this is the port to be used within the VR headset app. The robot_udp_port is the Ros2 node to the robot client.   
```ros2 launch franka_vr_teleop vr_control.launch.py --show-args```  
```ros2 launch franka_vr_teleop vr_control.launch.py```  

### Untested
bash
cd /opt/ros2_ws/src/franka-vr-teleop/robot_client/build
./franka_vr_control_client <ROBOT_IP>

Then, in a second terminal, ros2 launch franka_vr_teleop vr_control.launch.py. Keep your hand still at first and watch what the arm does before making real motions.