#!/bin/bash

SUDO='sudo -E'
# installs gcc ${OUR} and makes it system default
UBUNTU=4.8
OUR=${1:-4.9}

${SUDO} apt-add-repository -y "ppa:ubuntu-toolchain-r/test"
${SUDO} apt-get update
${SUDO} apt-get install gcc-${OUR} g++-${OUR} gcc-${OUR}-base libgcc-${OUR}-dev libstdc++-${OUR}-dev
${SUDO} update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-${UBUNTU} 100
${SUDO} update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-${OUR} 50
${SUDO} update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-${UBUNTU} 100
${SUDO} update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-${OUR} 50
${SUDO} update-alternatives --install /usr/bin/cpp cpp-bin /usr/bin/cpp-${UBUNTU} 100
${SUDO} update-alternatives --install /usr/bin/cpp cpp-bin /usr/bin/cpp-${OUR} 50
${SUDO} update-alternatives --set g++ /usr/bin/g++-${OUR}
${SUDO} update-alternatives --set gcc /usr/bin/gcc-${OUR}
${SUDO} update-alternatives --set cpp-bin /usr/bin/cpp-${OUR}

