FROM archlinux:latest

WORKDIR /opt
COPY dependencies.packages /opt/dependencies.packages
COPY models.json /opt/models.json.template
COPY entrypoint.sh /opt/entrypoint.sh
RUN pacman -Syy
RUN pacman -Sy --noconfirm --needed - < /opt/dependencies.packages
RUN npm install -g @earendil-works/pi-coding-agent
RUN chmod +x /opt/entrypoint.sh

RUN useradd -ms /bin/bash cad
RUN mkdir -p /home/cad/.pi/agent && chown -R cad:cad /home/cad/.pi
USER cad
WORKDIR /home/cad

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["bash"]
