# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

ARG UID=1000
ARG GID=1000
ARG VLLM_VERSION=0.27.0

# Ограничиваем потоки, чтобы не словить OOM при сборке
ENV MAX_JOBS=2
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    HF_HUB_CACHE=/models/hub \
    XDG_CACHE_HOME=/cache \
    TORCH_HOME=/cache/torch \
    VLLM_CACHE_ROOT=/cache/vllm \
    PYTHONPATH=/opt/vllm-extras

# Установка системных зависимостей (включая ccache, oneDNN, numa и tcmalloc)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake ninja-build git pkg-config libssl-dev libgomp1 curl \
      libnuma-dev numactl libnuma1 libtcmalloc-minimal4 libdnnl-dev ccache \
 && rm -rf /var/lib/apt/lists/*

# Копируем requirements (без vllm-cpu, так как собираем из исходников)
COPY docker/requirements.txt /tmp/requirements.txt

# Ставим базовые зависимости Python
RUN pip install --upgrade pip wheel setuptools \
 && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.txt

# --- СБОРКА vLLM ИЗ ИСХОДНИКОВ ---
RUN git clone --branch v${VLLM_VERSION} --depth 1 https://github.com/vllm-project/vllm.git /tmp/vllm
WORKDIR /tmp/vllm

# Устанавливаем сборочные и runtime-зависимости для CPU
RUN pip install -v -r requirements/build/cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu \
 && pip install -v -r requirements/cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Включаем ccache для сохранения скомпилированных объектов
ENV CMAKE_CXX_COMPILER_LAUNCHER=ccache
ENV CMAKE_C_COMPILER_LAUNCHER=ccache

# ЖЕСТКО ЗАДАЕМ ТАРГЕТ ПОД AVX2 И ОТКЛЮЧАЕМ AVX512
ENV VLLM_TARGET_DEVICE=cpu
ENV VLLM_CPU_AVX2=1
ENV VLLM_CPU_AVX512=0
ENV VLLM_CPU_AVX512VNNI=0

# Собираем и устанавливаем vLLM (с кэшем, чтобы при падении не начинать заново)
RUN --mount=type=cache,target=/root/.cache/ccache \
    python setup.py install

# Очищаем исходники для уменьшения размера образа
WORKDIR /home
RUN rm -rf /tmp/vllm /tmp/requirements.txt
# ---------------------------------

# Создание rootless пользователя
RUN groupadd --gid ${GID} app \
 && useradd --uid ${UID} --gid app --create-home --shell /bin/bash app

RUN mkdir -p /models /cache /opt/vllm-extras \
 && chown -R app:app /models /cache /opt/vllm-extras

# Кастомное логирование (скрытие промптов)
COPY --chown=app:app docker/logging/sitecustomize.py /opt/vllm-extras/sitecustomize.py

USER app
WORKDIR /home/app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["python", "-m", "vllm.entrypoints.openai.api_server"]
