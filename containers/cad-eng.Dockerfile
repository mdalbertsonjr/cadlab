FROM python-dep:latest

WORKDIR /opt
COPY cad-eng.packages /opt/cad-eng.packages
RUN pacman -Syu --noconfirm
RUN pacman -S --noconfirm --needed - < /opt/cad-eng.packages

COPY claude-entrypoint.sh /usr/local/bin/claude-entrypoint.sh
RUN chmod +x /usr/local/bin/claude-entrypoint.sh

ENV PYTHONPATH=/usr/lib/freecad/lib

USER developer
RUN curl -fsSL https://claude.ai/install.sh | bash
WORKDIR /home/developer
RUN echo "export PATH=$PATH:~/.local/bin" >> .bashrc

ENTRYPOINT ["/usr/local/bin/claude-entrypoint.sh"]
CMD ["bash"]
