# Deployment State

| State | Meaning |
|---|---|
| SOURCE CREATED | Files exist in a working tree |
| LOCAL IMPLEMENTATION | Code is wired locally |
| TESTED | Named checks passed in a stated environment |
| COMMITTED | Git commit exists |
| REMOTE DEPLOYED | Hosting platform accepted a deployment |
| PRODUCTION RUNNING | Live process and endpoints respond |
| PRODUCTION ACCEPTED | Required acceptance evidence passes |

These states remain separate. Code/configuration alone proves only `SOURCE CREATED`. Context.dev commercial production authorization remains `BLOCKED` until reviewed written scope evidence is recorded.
