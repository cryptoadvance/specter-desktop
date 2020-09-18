FROM registry.gitlab.com/cryptoadvance/specter-desktop/python:3.8.5-bionic

RUN apt-get update && apt-get install -y --no-install-recommends libusb-1.0-0-dev libudev-dev

RUN apt-get install -y --no-install-recommends libgl1-mesa-dri gvfs gvfs-libs \
        libdrm-amdgpu1 libdrm-nouveau2 libdrm-radeon1 libedit2 libelf1 libllvm10 \
        libvulkan1 libzstd1 libtdb1 libcanberra-gtk3-0 virtualenv libcanberra-gtk3-module