# Security policy and vulnerability reporting

USB Fix Tool can invoke privileged Windows operations such as CHKDSK, DiskPart and formatting. A disk selection or command-construction defect can have significant data-loss consequences.

## Scope

The Windows desktop application is located in `usb-fix-tool/desktop/`. The repository also includes a static website and separate demo web scaffolding. There is **no declared security support window or response-time guarantee**.

## Reporting a vulnerability

If GitHub's **Private vulnerability reporting** option is enabled for this repository, use **Security → Report a vulnerability** to contact the maintainer privately.

If private reporting is unavailable, avoid disclosing exploitation details or sensitive device information in a public issue. Contact the repository maintainer to arrange a suitable private communication channel first; you may open a general issue asking for a secure reporting route **without technical exploit details**.

A useful report includes:
- Affected source file and application version.
- Reproducible scenario, Windows environment and device class.
- Security or data-loss impact, and whether administration rights are needed.
- A minimal example using dummy data or a disposable test drive.
- Redacted logs, with device serials, credentials and personal paths removed.

## User precautions

- Back up files before modifying storage.
- Confirm disk number, device identity and partition on every privileged operation.
- Avoid running unknown builds or downloading ZIP files from unverified domains.
- Prefer reproducing any suspected defect on disposable media or with mocks.

See [Safety and data loss](docs/SAFETY.md) for operational details.
