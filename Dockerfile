# Official ROS 2 Jazzy Base image, built on Ubuntu 24.04 Noble.
# This is the non-Desktop ROS image: no RViz, Gazebo, or other GUI stack.
FROM ros:jazzy-ros-base-noble

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=sydney
ARG USER_UID=1000
ARG USER_GID=1000
ENV ROS_DISTRO=jazzy
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-c"]

# Install system packages with APT. ROS remains managed by APT; the Python SDK
# will be installed separately into a virtual environment below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        wget \
        # Python venv dependencies
        python3-colcon-common-extensions \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3-rosdep \
        sudo \
        # Web Camera Build Dependencies
        udev \
        usbutils \
        # PyQt5 System Libraries for the RealHand GUI
        python3-pyqt5 \
        # Ros Demo Nodes
        ros-jazzy-demo-nodes-cpp \
        # RealSense Build Dependencies
        libssl-dev \
        libusb-1.0-0-dev \
        pkg-config \
        libgtk-3-dev \
        libglfw3-dev \
        libglu1-mesa-dev \
        freeglut3-dev \
        # Franka Robotics System Compilation Prerequisites
        libeigen3-dev \
        libpoco-dev \
        libfmt-dev \
        pybind11-dev \
        libgmock-dev \
    && if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then rosdep init; fi \
    && rosdep update \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# Non-Root Developer User
# ==============================================================================
# Create a non-root developer user. The groups allow common serial, USB,
# camera, and GPU/render access when the corresponding host devices are passed
# through by docker-compose.yml.
RUN if getent group "${USER_GID}" >/dev/null; then \
         # If GID 1000 exists, just rename it to your username
         EXISTING_GROUP=$(getent group "${USER_GID}" | cut -d: -f1); \
         groupmod -n "${USERNAME}" "${EXISTING_GROUP}"; \
     else \
         # If GID 1000 doesn't exist, create it cleanly
         groupadd --gid "${USER_GID}" "${USERNAME}"; \
     fi \
     && if getent passwd "${USER_UID}" >/dev/null; then \
         # If UID 1000 exists (like user 'ubuntu'), reuse and rename it
         EXISTING_USER=$(getent passwd "${USER_UID}" | cut -d: -f1); \
         usermod -l "${USERNAME}" -d "/home/${USERNAME}" -m "${EXISTING_USER}"; \
     else \
         # If UID 1000 doesn't exist, create your user cleanly
         useradd --uid "${USER_UID}" --gid "${USER_GID}" --create-home --shell /bin/bash "${USERNAME}"; \
     fi \
     && for group in dialout plugdev video render; do \
          getent group "${group}" >/dev/null || groupadd "${group}"; \
          usermod --append --groups "${group}" "${USERNAME}"; \
        done \
     && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
     && chmod 0440 "/etc/sudoers.d/${USERNAME}"
# ==============================================================================

# ==============================================================================
# Python Virtual Environment
# ==============================================================================
# Create an isolated Python 3.12 environment. --system-site-packages lets the
# venv import ROS Python modules such as rclpy, while pip installs SDK packages
# only inside /home/${USERNAME}/.venv and never overwrites Ubuntu/ROS packages.
RUN python3.12 -m venv --system-site-packages "/home/${USERNAME}/.venv"

COPY requirements.txt /tmp/requirements.txt

RUN "/home/${USERNAME}/.venv/bin/python" -m pip install --no-cache-dir --upgrade pip \
    && "/home/${USERNAME}/.venv/bin/python" -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/.venv"

ENV VIRTUAL_ENV=/home/${USERNAME}/.venv
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}
ENV PYTHONUNBUFFERED=1
# ==============================================================================

# ==============================================================================
# INTEL REALSENSE SDK BUILD FROM SOURCE (C++ and Python Wrapper)
# ==============================================================================
WORKDIR /opt
RUN git clone https://github.com/realsenseai/librealsense.git \
    && cd librealsense \
    && mkdir build && cd build \
    && cmake ../ \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_PYTHON_BINDINGS:bool=true \
        -DPYTHON_EXECUTABLE=/home/${USERNAME}/.venv/bin/python \
        -DBUILD_EXAMPLES=true \
        -DFORCE_RSUSB_BACKEND=true \
    && make -j$(nproc) \
    && make install \
    && cd /opt && rm -rf librealsense

# Configure Global Python Paths so pyrealsense2 is discoverable inside/outside venv
ENV PYTHONPATH=$PYTHONPATH:/usr/local/lib:/usr/local/lib/python3.12/pyrealsense2
# ==============================================================================

# ==============================================================================
# STANDALONE C++ LIBFRANKA BUILD FROM SOURCE
# ==============================================================================
WORKDIR /tmp
RUN wget https://github.com/frankarobotics/libfranka/releases/download/0.21.3/libfranka_0.21.3_noble_amd64.deb \
    && dpkg -i libfranka_0.21.3_noble_amd64.deb \
    && rm libfranka_0.21.3_noble_amd64.deb

# Configure Global Python Paths so pyrealsense2 and your virtual environment match perfectly
ENV PYTHONPATH=/home/${USERNAME}/.venv/lib/python3.12/site-packages:/usr/local/lib:/usr/local/lib/python3.12/pyrealsense2:$PYTHONPATH
# ==============================================================================

# ==============================================================================
# ROS 2 UNDERLAY WORKSPACE (realsense-ros, realbot-ros2, franka_ros2)
# ==============================================================================
WORKDIR /opt/ros2_ws
RUN mkdir -p src \
    && cd src \
    && git clone https://github.com/realsenseai/realsense-ros.git -b ros2-master \
    && git clone https://github.com/RealHand-Robotics/realbot-ros2-sdk.git -b main \
    && git clone https://github.com/frankarobotics/franka_ros2.git -b jazzy \
    && cd /opt/ros2_ws \
    && source /opt/ros/jazzy/setup.bash \
    && vcs import src < src/franka_ros2/dependency.repos --recursive --skip-existing \
    && touch src/franka_ros2/franka_gazebo/COLCON_IGNORE \
    && touch src/franka_ros2/franka_mobile/COLCON_IGNORE \
    && touch src/franka_ros2/franka_mobile_fr3_duo_moveit_config/COLCON_IGNORE \
    && touch src/franka_ros2/mobile_fr3_duo_trajectory_controller/COLCON_IGNORE \
    && touch src/libfranka/COLCON_IGNORE \
    && apt-get update \
    && rosdep update \
    && rosdep install --from-paths src --ignore-src --rosdistro jazzy -y \
       --skip-keys="librealsense2 realhand libfranka zed_wrapper robotiq_description olive_ros2 franka_gazebo franka_gazebo_hardware franka_gazebo_bringup franka_gripper franka_mobile franka_mobile_fr3_duo_moveit_config mobile_fr3_duo_trajectory_controller robotiq_driver olv_module_descriptions" \
    && rm -rf /var/lib/apt/lists/*

RUN source /opt/ros/jazzy/setup.bash \
    && cd /opt/ros2_ws \
    && colcon build \
       --parallel-workers 2 \
       --event-handlers console_cohesion+ \
       --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
# ==============================================================================

# Set up a writable ROS workspace for the non-root user.
RUN mkdir -p "/home/${USERNAME}/ros2_ws/src" \
    && chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/ros2_ws"
USER ${USERNAME}
WORKDIR /home/${USERNAME}/ros2_ws

# Source ROS for interactive and non-interactive Bash commands. The venv is
# already active through PATH/VIRTUAL_ENV, so `python` is the SDK-safe Python.
# Update terminal sourcing configs to include BOTH workspaces automatically
RUN echo "source /opt/ros/jazzy/setup.bash" >> /home/${USERNAME}/.bashrc && \
    echo "source /opt/ros2_ws/install/setup.bash" >> /home/${USERNAME}/.bashrc && \
    echo "source /home/${USERNAME}/.venv/bin/activate" >> /home/${USERNAME}/.bashrc && \
    echo "export PYTHONPATH=\$PYTHONPATH:/home/${USERNAME}/.venv/lib/python3.12/site-packages" >> /home/${USERNAME}/.bashrc

ENV BASH_ENV=/home/${USERNAME}/.bashrc
CMD ["bash"]
