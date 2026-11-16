# Issues

Issues are optional. Michael can give work directly in a session. Use an issue when the
work spans sessions, needs Michael's hands, or he wants a record.

## Labels

| Label | Meaning |
|---|---|
| `software-lead`, `hardware-lead`, `pm`, `surge` | Work for that role, in this repository |
| `verification-lead` | Strict-track or review work, in [the verification repository](https://github.com/mmsanders/digital-tape-verification/issues?q=is%3Aissue%20is%3Aopen%20label%3Averification-lead) |
| `michael` | Needs Michael: a purchase, a bench check, a decision ([open](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael)) |
| `intake` | An idea recorded, not scheduled ([intake](INTAKE.md)) |

## Writing one

Say the outcome wanted, what is out of scope, and what Michael will check at the end. A
few sentences. No hash lists; link whatever the reader needs.

## Working one

1. Michael starts it. Nothing starts from a notification, an old event or a closed issue.
2. Do the work on a branch, open a PR, and let the PR carry the detail.
3. Comment once at the end: what was done, what was not, what Michael does next. Put
   `Closes #n` in the PR so merging closes the issue.
4. If you are blocked, say on what in one line and stop. Do not poll or wait.

Strict-track work (engine, format) adds the steps in [ENGINE-CHANGES](ENGINE-CHANGES.md).
