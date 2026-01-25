FROM ghcr.io/astral-sh/uv:0.9.26-python3.14-trixie-slim


RUN apt update && \
    apt install -y git && \
    apt clean && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace