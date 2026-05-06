FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY .devcontainer/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Create a non-root user
RUN useradd -m -s /bin/bash vscode

WORKDIR /workspace
ENV PYTHONPATH=/workspace

USER vscode
CMD ["/bin/bash"]