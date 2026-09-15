FROM us-central1-docker.pkg.dev/sara-soverigne-modules/sara-samcr/sara-evolution-engine-cre-fix@sha256:a23de9bcc6a5f23bb0ef22224f6e5fbca504d9737cb69cf50d273e9648f8511e
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quantum_patch.py .
COPY main_patched.py .
ENV PORT=8080
EXPOSE 8080
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "main_patched:app"]
