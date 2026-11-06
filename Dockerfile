FROM ros:lyrical-ros-core-resolute

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    QML_IMPORT_PATH=/app \
    SDL_AUDIODRIVER=dummy

RUN apt-get update && apt-get install -y --no-install-recommends \
    libdbus-1-3 \
    libegl1 \
    libegl-mesa0 \
    libfontconfig1 \
    libfreetype6 \
    libgl1 \
    libgl1-mesa-dri \
    libglib2.0-0 \
    libglx-mesa0 \
    libice6 \
    libopengl0 \
    libsm6 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-cursor0 \
    libxcb-glx0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/runtime-dir \
    && chown 1000:1000 /tmp/runtime-dir \
    && chmod 0700 /tmp/runtime-dir

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-cache \
    && chmod -R a+rX /opt/venv

CMD ["python", "hal062_application/main.py"]