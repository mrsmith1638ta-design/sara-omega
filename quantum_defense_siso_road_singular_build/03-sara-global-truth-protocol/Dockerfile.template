FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY integrity_patch.py .
COPY main_patched.py .
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn main_patched:app --host 0.0.0.0 --port ${PORT}"]
