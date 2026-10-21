# Changelog

Changes proposed after the inspected source snapshot are listed under Unreleased. No release dates or historical release entries are inferred from UI version labels.

## Unreleased

### Documentation

- Replace the root placeholder README with an English overview grounded in the desktop and web sources.
- Add usage, installation/build and storage-safety guides, including differences between legacy repair wrappers and the partition backend.
- Add contribution, support, security reporting and issue/PR guidance.
- Record suggested repository description/topics and connector limitations.

## Source baseline

The inspected default-branch commit is `aab0c46320bba6d2cf6e7726506c6976a190ee44`. Its desktop `main.py` declares `APP_VERSION = "2.3.1"`; the frontend package separately declares `0.1.0`. Existing component documentation refers to earlier feature versions, but those labels have not been reconstructed as released changelog entries. The GitHub releases collection was empty during inspection. These documentation changes do not change application behavior or publish a binary.
