# docker_sjsu_fr3vla

View docker container information:
'''docker ps'''

Docker compose build and run:
Build and start the container using your compose configurations
'''docker compose up -d'''

Drop into the interactive shell to see your files and run scripts
'''docker compose exec -it ros2 bash'''

Close and exit docker container
'''docker compose down '''

Enter running docker container in a new terminal
'''sudo docker exec -it <CONTAINER_ID> bash'''

Commands which may be needed to pass through host computer for hardware access
Pass through display to host computer
'''xhost +local:docker'''

Access video
'''sudo chmod 666 /dev/video*'''
