# Contributing to USB Fix Tool

Thanks for helping improve the project. Contributions should preserve user data safety, source transparency and accurate documentation.

## Before proposing a change

- Check existing issues and repository history for similar work.
- Open a focused issue describing the problem, Windows version, target device type, reproduction steps and **redacted** logs.
- For behavior affecting disks, explain whether the action writes data, changes a partition table, uses elevated privileges, or invokes CHKDSK/DiskPart.

## Local setup

Follow [Development and build guide](docs/DEVELOPMENT.md). The desktop project lives in `usb-fix-tool/desktop/`, **not** the root-level React/FastAPI starter files.

## Pull request guidelines

1. Keep the change focused and describe affected code and user-facing behavior.
2. Do not weaken target identity verification, confirmation dialogs, protected-partition checks or failure reporting without explicit justification.
3. Add or adapt tests where practical; use disposable media for any manual destructive test.
4. Record **which tests were actually run**, on which environment, and their observed outcomes. Do not claim tests passed without executing them.
5. Update documentation for changed options, commands or safety behavior.
6. Avoid embedding personal information, USB serials, filesystem contents, secrets, binaries or unverifiable claims.
7. Do not introduce a copyright or license declaration on behalf of the maintainer.

The repository currently has **no declared source license**. Being publicly readable does not grant unrestricted permission to reuse or distribute its contents. Contact the repository maintainer regarding rights and contribution terms before submitting substantial contributions.

## Reporting a bug

Use the provided issue template when possible. Include the app version from `main.py`, Windows build, the relevant tab and exact steps. **Never post unredacted serial numbers or private data.**

## Security issues

Follow [SECURITY.md](SECURITY.md); do not publicly disclose weaponizable disk-targeting vulnerabilities with full exploitation steps.
