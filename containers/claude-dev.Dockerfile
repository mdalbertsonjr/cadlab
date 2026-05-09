FROM base-dev:latest

USER root
COPY claude-entrypoint.sh /usr/local/bin/claude-entrypoint.sh
RUN chmod +x /usr/local/bin/claude-entrypoint.sh

USER developer
RUN curl -fsSL https://claude.ai/install.sh | bash
WORKDIR /home/developer
RUN echo "export PATH=$PATH:~/.local/bin" >> .bashrc

ENTRYPOINT ["/usr/local/bin/claude-entrypoint.sh"]
CMD ["bash"]
