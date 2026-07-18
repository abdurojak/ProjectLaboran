FROM python:3.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-build.txt ./
RUN python -m pip install -r requirements-build.txt \
    && python -m pip wheel --wheel-dir /wheels -r requirements.txt

COPY . .
RUN python deployment/build_protected_artifact.py \
      --source . \
      --staging /protected-release \
      --output /tmp/projectlaboran.protected.tar.gz \
      --allowlist deployment/protected_modules.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       default-mysql-client libmariadb3 libgl1 libglib2.0-0 poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 labhub \
    && useradd --uid 1000 --gid labhub --home-dir /app --shell /usr/sbin/nologin labhub

COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt

WORKDIR /app
COPY --from=builder --chown=labhub:labhub /protected-release /app
RUN chmod 0755 /app/deployment/container-entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R labhub:labhub /app/staticfiles /app/media

USER labhub
EXPOSE 8000
VOLUME ["/app/media"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health/', timeout=3)" || exit 1

ENTRYPOINT ["/app/deployment/container-entrypoint.sh"]
