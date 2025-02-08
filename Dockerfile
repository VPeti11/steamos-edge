FROM linuxserver/steamos:latest

ENV LANG=C.UTF-8

RUN sudo pacman -Syu --noconfirm \
    && sudo pacman -S --noconfirm git archiso zsh \
    && sudo pacman -Scc --noconfirm

RUN git clone https://gitlab.com/jupiter-linux/steamos-sdk.git

RUN chmod +x build.sh

RUN ./build

CMD ["zsh"]
