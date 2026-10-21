# Contributing

Use a focused pull request and describe the problem, resulting behavior and validation. Read [installation](docs/INSTALLATION.md) and [safety](docs/SAFETY.md) first. Preserve unrelated files and never test destructive changes on valuable disks.

For disk-related changes, explain the target-selection path, physical identity revalidation, refusal cases, command arguments, partial-failure behavior and output handling. Add meaningful regression coverage for changed safety behavior. Mocks must never silently fall through to real disk commands. Review tests before running them; the existing runner and its environment requirements are documented in the installation guide.

Documentation should match executable code. Distinguish source versions from published releases, free-space tests from full-device coverage, and local reports from independent certification. Record commands actually run, their environment and outcomes; mark skipped checks explicitly.

Before submitting:
- Review the complete diff for accidental source, binary, credential or device-data changes.
- Validate relative links and commands against the actual repository layout.
- Include relevant regression/build results and any unverified Windows behavior.
- Redact serials, usernames, private paths and disk contents from logs/screenshots.

Be respectful, give reproducible evidence and discuss technical disagreements constructively. Report sensitive issues using [SECURITY](SECURITY.md), not a public exploit report. No project license has been selected in this repository; do not assume public availability grants redistribution rights or add licensing terms without the owner's decision.
