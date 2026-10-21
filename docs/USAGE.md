# Desktop usage

Read [SAFETY](SAFETY.md) first and [install the desktop app](INSTALLATION.md). Work only on backed-up, replaceable storage.

## Capacity Test

1. Connect the intended drive, wait for the background scan, then use Refresh if necessary.
2. Select the target and verify its letter, label and capacity. Close other applications writing to it.
3. Choose Full capacity test, Custom size, or Quick verification (1 GB sample). Full means testable free space; Quick is at most 1 GiB. A partial test cannot establish the full capacity.
4. If matching leftover test files are found, inspect them before approving cleanup.
5. Start Test and let both writing and verification finish. Use Stop Test and its confirmation if needed; allow cleanup to complete.
6. Read tested/verified/corrupted amounts, errors and the activity log. A stopped or errored run is incomplete. A PASS applies only to the tested bytes.

The test writes real data; it is not a read-only scan. A drive that falsely maps different addresses to the same storage can corrupt existing files even though the program writes filesystem free space.

## USB Partitions

1. Open USB Partitions and wait for the eligible-device scan.
2. Compare the selected physical disk's model, identity and capacity with Windows Disk Management. An omitted device may be deliberately ineligible; do not bypass the filter.
3. Inspect the partition table and unallocated space.
4. Select a partition for Delete or Format, or choose maximum/custom size in unallocated space for Create.
5. Review the confirmation and log. Protected partitions and read-only disks are blocked. The partition backend blocks FAT32 formatting above its 32 GiB constant (the UI labels this 32 GB); choose exFAT/NTFS or an appropriately smaller partition.

Deleting and formatting lose data. Creating a partition changes the layout. Refresh after completion and confirm the resulting state before further changes.

## Fix Fake Drive and re-verification

The action is conditional: a qualifying failed Full test must provide a usable boundary and an eligible USB identity. Some failed runs cannot establish this and will not offer automatic repair.

1. Review the proposed usable capacity and safety margin. This is an inference from a filesystem test, not a hardware guarantee.
2. Open Fix Fake Drive and review the identified disk, partitions to be removed, final size and filesystem. The size may be reduced.
3. Confirm only after backing up everything on the physical disk. Existing partitions are deleted.
4. On complete success, use Re-verify Repaired Drive. It resolves the original device identity and repaired partition, then runs another Full capacity test after confirmation.
5. If repair fails or only partially completes, preserve the log and inspect the layout; no automatic rollback restores files.

A smaller partition does not repair flash chips or counterfeit firmware.

## Reports

The UI exposes report actions only for qualifying states. A successful re-verification can unlock a Verification Certificate; a qualifying failed capacity result can offer a Proof Report and claim text. Save the HTML report, open it in a browser, then use Print / Save as PDF if desired.

Review the contents before sharing. Serial masking does not make the model, fingerprint or logs anonymous. Report labels do not establish independent certification or legal proof.

## Repair Tools

Use caution: this tab uses the older wrappers described in [Different safety paths](SAFETY.md#different-safety-paths).

- Run CHKDSK changes the filesystem using `/F /R /X`; it is not a read-only check.
- Format uses the selected filesystem and label and invokes a quick format.
- Advanced Repair cleans the entire mapped physical disk and recreates/formats a partition, affecting all its volumes.
- Assign Letter selects partition 1 of the mapped disk; check the resulting assignment.

The confirmation checkbox and second dialog cover Format and Advanced Repair, not every action. Review the actual command output; do not rely solely on the success banner. The footer's recovery link is an external placeholder, not built-in file recovery.

## Troubleshooting

- **Empty/failed scan:** reconnect the intended device, wait and Refresh; inspect the log. Eligibility filtering can intentionally hide devices.
- **Access denied/in use:** close programs using the disk and check administrator privileges. Reconfirm the target after restarting.
- **RAW/unformatted target:** free-space testing needs an accessible writable filesystem. If files matter, stop before formatting.
- **Partial repair:** preserve the log and inspect the layout before deciding on recovery or manual partition creation/formatting.
- **Startup/build error:** run from a visible terminal using the installation guide and include the error and dependency versions in a sanitized issue.
