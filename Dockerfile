FROM debian:bullseye as builder

# Install build dependencies for nsjail
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    git \
    flex \
    bison \
    libnl-route-3-dev \
    protobuf-compiler \
    libprotobuf-dev \
    ca-certificates \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Clone the nsjail repository
WORKDIR /build
RUN git clone --depth 1 https://github.com/google/nsjail.git .

# Compile nsjail
RUN make

# ---- Stage 2: Final Image ----
FROM python:3.10-slim-bullseye

# Labels for metadata
LABEL maintainer="Python Sandbox Team" \
      description="Python Code Execution Sandbox API" \
      version="latest" \
      repository="python-sandbox-478302" \
      org.opencontainers.image.source="https://github.com/your-org/python-sandbox"

WORKDIR /app

# Install runtime dependencies
COPY requirements.txt .
RUN apt-get update -y
RUN apt-get install -y --no-install-recommends \
    # procps is for checking processes if debugging the container
    procps \
    # RUNTIME library needed by the compiled nsjail binary
    libnl-route-3-200 \
    libprotobuf23 \
    && pip install --no-cache-dir -r requirements.txt \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled nsjail binary
COPY --from=builder /build/nsjail /usr/local/bin/nsjail

# Copy configuration and application code
COPY nsjail.cfg .
COPY app.py .
COPY executor.py .
COPY config.py .
COPY sandbox.py .

# === Verification Step ===
# Show paths during build to help configure nsjail.cfg correctly
RUN echo "--- Verifying paths for nsjail.cfg ---" && \
    echo "Python executable:" && which python && \
    echo "nsjail executable:" && which nsjail && \
    echo "Python library path:" && python -c "import sys; print(sys.prefix)" && \
    echo "Python site-packages path:" && python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())" && \
    echo "Contents of Python lib dir (check if matches nsjail mount src):" && ls -ld $(python -c "import sys; print(sys.prefix)")/lib/python* && \
    echo "--- Verification End ---"

# Make port 8080 available
EXPOSE 8080

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["python", "app.py"]
