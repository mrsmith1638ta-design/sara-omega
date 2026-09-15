FROM python:3.12-slim
WORKDIR /workload
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENV PYTHONUNBUFFERED=1
ENV PROJECT_ID=sara-soverigne-modules
ENV KMS_LOCATION=us-central1
ENV KMS_KEYRING=sara-cipmu-confidential
ENV KMS_KEY=cipmu-seal-key
ENV ATTESTATION_AUDIENCE=sara-cipmu-step6e
CMD ["python", "main.py"]
