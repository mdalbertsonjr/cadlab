FROM archlinux:latest

WORKDIR /opt
COPY base.packages /opt/base.packages
RUN pacman -Syy
RUN pacman -Sy --noconfirm --needed - < /opt/base.packages 

RUN useradd -ms /bin/bash developer
