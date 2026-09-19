# Use These v1.3 Scripts

Use the `_v13` scripts in Cloud Shell:

```bash
cd ~/sara_quantum_defense/quantum-defense-v13-build
bash create_pqc_secrets_v13.sh
bash build_one_candidate_v13.sh sara-nexus-ppsim
```

Then deploy one service at a time in the approved order:

```bash
bash build_one_candidate_v13.sh sara-security-fabric
bash build_one_candidate_v13.sh sara-global-truth-protocol
bash build_one_candidate_v13.sh sara-evolution-engine
bash build_one_candidate_v13.sh sara-nexus-cipmu
bash build_one_candidate_v13.sh raft-node-n1
bash build_one_candidate_v13.sh raft-node-n2
bash build_one_candidate_v13.sh raft-node-n3
```

Each candidate is built from the currently serving 100 percent Cloud Run revision image, deployed with `--no-traffic --tag candidate`, then verified before any traffic shift.

Shift traffic only after `/health` and the patch endpoint return `HTTP 200`:

```bash
gcloud run services update-traffic SERVICE_NAME \
  --project=sara-soverigne-modules \
  --region=us-central1 \
  --to-tags=candidate=100 \
  --quiet
```
