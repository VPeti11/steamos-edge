FROM archlinux:latest

ENV LANG=C.UTF-8

RUN sudo pacman -Syu --noconfirm \
    && sudo pacman -S --noconfirm git archiso bash \
    && sudo pacman -Scc --noconfirm

RUN git clone https://gitlab.com/edgedev1/steamos-edge.git && cd steamos-edge

RUN chmod +x mkedgescript

RUN ./mkedgescript

CMD ["bash"]
