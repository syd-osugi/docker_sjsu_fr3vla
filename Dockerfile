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
        python3-colcon-common-extensions \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3-rosdep \
        sudo \
        udev \
        usbutils \
        python3-opencv \
        ros-jazzy-demo-nodes-cpp \
    && if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then rosdep init; fi \
    && rosdep update \
    && rm -rf /var/lib/apt/lists/*

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

# Create an isolated Python 3.12 environment. --system-site-packages lets the
# venv import ROS Python modules such as rclpy, while pip installs SDK packages
# only inside /home/${USERNAME}/.venv and never overwrites Ubuntu/ROS packages.
RUN python3.12 -m venv --system-site-packages "/home/${USERNAME}/.venv" \
    && "/home/${USERNAME}/.venv/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/.venv"
ENV VIRTUAL_ENV=/home/${USERNAME}/.venv
ENV PATH=${VIRTUAL_ENV}/bin:${PATH}
ENV PYTHONUNBUFFERED=1

# Set up a writable ROS workspace for the non-root user.
RUN mkdir -p "/home/${USERNAME}/ros2_ws/src" \
    && chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/ros2_ws"
USER ${USERNAME}
WORKDIR /home/${USERNAME}/ros2_ws

# Source ROS for interactive and non-interactive Bash commands. The venv is
# already active through PATH/VIRTUAL_ENV, so `python` is the SDK-safe Python.
# RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> "/home/${USERNAME}/.bashrc"
RUN echo "source /opt/ros/jazzy/setup.bash" >> /home/sydney/.bashrc && \
    echo "source /home/sydney/.venv/bin/activate" >> /home/sydney/.bashrc

ENV BASH_ENV=/home/${USERNAME}/.bashrc
CMD ["bash"]

