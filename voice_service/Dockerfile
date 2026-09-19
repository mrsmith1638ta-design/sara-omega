FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY voice_service/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY voice_service ./voice_service

EXPOSE 5000

CMD ["sh", "-lc", "python -m voice_service.bootstrap && exec uvicorn voice_service.app:create_default_app --factory --host 0.0.0.0 --port 5000"]
