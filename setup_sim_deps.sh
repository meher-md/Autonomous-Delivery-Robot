#!/usr/bin/env bash
set -eo pipefail

sudo apt-get update
sudo apt-get install -y \
  ignition-fortress \
  libignition-gazebo6-dev \
  ros-humble-compressed-image-transport \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-nav2-common \
  ros-humble-robot-localization \
  ros-humble-ros-gz-bridge \
  ros-humble-ros-gz-sim \
  ros-humble-slam-toolbox

echo "Simulation dependencies installed."
