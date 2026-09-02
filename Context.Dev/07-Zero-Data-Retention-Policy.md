# Zero Data Retention Policy

Sensitive requests requiring Zero Data Retention execute only when both contractual ZDR entitlement and support for the exact endpoint/workflow are verified.

Unknown entitlement, unsupported endpoints, ambiguous retention, or unavailable evidence fails closed with `ZDR_NOT_VERIFIED`. Redaction or a less-sensitive workflow is a new request, not a silent downgrade.
