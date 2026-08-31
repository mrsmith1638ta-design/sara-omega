# SARA-OMEGA V3.2.1 Privacy Notice

The SARA-OMEGA V3.2.1 ChatGPT action integration uses read-only HTTPS endpoints hosted at `sara-omega-production.up.railway.app` to report runtime identity, readiness, and production-acceptance evidence.

These read-only action endpoints do not require or return the Railway `OWNER_TOKEN`, the fail-safe master key, API keys, passwords, or other secret values. The integration is designed to expose only non-secret operational status needed to attest that the connected SARA-OMEGA runtime is live and production-accepted.

Requests made by ChatGPT actions may be processed by the hosting platform and by OpenAI according to their respective terms and privacy policies. Do not place passwords, private keys, authentication tokens, or other secrets into prompts intended for these read-only status actions.

Operational endpoint: https://sara-omega-production.up.railway.app

Release: SARA-OMEGA V3.2.1
