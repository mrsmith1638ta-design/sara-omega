# Architecture and Tool Routing

The public Custom GPT reads only sanitized `/context-dev/status`. It cannot access the owner-only evaluation endpoint, credentials, evidence, or vendor transport.

Railway routes a future request through authenticated server request, authorization gate, Terms-hash gate, automation/scope gate, target-rights gate, ZDR gate, and only then a server-side vendor adapter. Pending-MSA configuration stops before transport.

Credentials are forbidden in browsers, Custom GPT instructions, public schemas, clients, and customer-visible output.
