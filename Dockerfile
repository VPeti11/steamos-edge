FROM linuxserver/steamos:latest

ENV LANG=C.UTF-8

RUN sudo pacman -Syu --noconfirm \
    && sudo pacman -S --noconfirm git archiso bash \
    && sudo pacman -Scc --noconfirm

RUN git clone https://gitlab.com/jupiter-linux/steamos-edge.git && cd steamos-edge

RUN ./build.sh

CMD ["bash"]
