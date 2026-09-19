FROM us-central1-docker.pkg.dev/sara-soverigne-modules/sara-quantum-defense/raft-node-n1-step6f@sha256:80d5725a41723303a64cc384b51aa41cdc75215db1e60d12ed2dcedd985906ce
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY raft_pqc_patch.py .
COPY main_patched.py .
COPY test_raft_pqc_patch.py .
RUN python -m unittest -v test_raft_pqc_patch.py
ENV PORT=8080
EXPOSE 8080
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--worker-class", "gthread", "main_patched:app"]