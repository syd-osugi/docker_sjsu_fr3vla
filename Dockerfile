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
# INTEL REALSENSE ROS 2 WRAPPER INSTALLATION
# ==============================================================================
# Build workspace under root first to handle rosdep configurations cleanly
RUN mkdir -p /opt/ros2_ws/src \
    && cd /opt/ros2_ws/src \
    && git clone https://github.com/realsenseai/realsense-ros.git -b ros2-master \
    && cd /opt/ros2_ws \
    && source /opt/ros/jazzy/setup.bash \
    && apt-get update \
    && rosdep install -i --from-path src --rosdistro jazzy --skip-keys=librealsense2 -y \
    && colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf /var/lib/apt/lists/*

# Fix folder ownership so your local workspace remains isolated
RUN chown -R "${USERNAME}:${USERNAME}" /opt/ros2_ws
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
    echo "source /home/${USERNAME}/ros2_ws/install/setup.bash" >> /home/${USERNAME}/.bashrc

ENV BASH_ENV=/home/${USERNAME}/.bashrc
CMD ["bash"]

