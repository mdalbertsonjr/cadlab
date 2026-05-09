FROM archlinux:latest

WORKDIR /opt
COPY dependencies.packages /opt/dependencies.packages
RUN pacman -Syy
RUN pacman -Sy --noconfirm --needed - < /opt/dependencies.packages 
RUN npm install -g @earendil-works/pi-coding-agent

RUN useradd -ms /bin/bash cad
USER cad
