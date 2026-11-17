FROM python:3.13-slim

WORKDIR /app

COPY pawchive_dl/ ./pawchive_dl/
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir .

RUN mkdir -p /media /appdata
VOLUME ["/media", "/appdata"]

ENTRYPOINT ["pawchive-dl"]
