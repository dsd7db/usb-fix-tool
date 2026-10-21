# Security reporting

## Scope and support

This repository contains a privileged Windows storage utility and separate web starter components. No maintained-version support matrix, response-time commitment or security audit is declared. The desktop source version is not evidence of a signed or audited release.

Misidentifying a disk, bypassing operation guards, command injection, unexpected destructive behavior and leaking device/user information are security-relevant. See [storage safety](docs/SAFETY.md) for operational risks and known differences between command paths.

## Report privately

Do not publish secrets, disk contents, full device serials or a working destructive exploit in an issue.

If GitHub's “Report a vulnerability” option is available on this repository's Security page, use it for a private report. Its availability has not been verified, and no security email address is configured by this policy. If no private channel is available, open a minimal public issue asking the maintainer to establish one, without sensitive details or exploit instructions.

Include affected commit/version, OS, relevant dependency versions, impact, a safe reproduction using mocks or disposable media, and redacted logs. Never ask others to run a destructive proof of concept on their own disks.

## Safe handling

Keep a separate verified backup before storage operations. Do not expose the unauthenticated FastAPI starter service publicly without a separate security review. Review external download URLs and dependencies before installing or distributing builds. HTML reports are local statements and may still contain identifying information even with masked serials.
