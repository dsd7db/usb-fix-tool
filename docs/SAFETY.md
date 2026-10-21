# Storage safety

## Before any operation

1. Back up files to a different physical device and verify the backup. If irreplaceable data is already missing or the device is failing, stop writing and seek a recovery workflow first.
2. Disconnect unrelated removable disks. Check model, capacity, serial where available, drive letter and physical disk number against Windows Disk Management.
3. Close applications using the target. Keep power and the USB connection stable. Never swap devices during a scan, confirmation or operation.
4. Read the preview and log. Cancel if identification is ambiguous, a value changes, or the selected disk is unexpected. Administrator access increases the consequences of a mistake.

UI confirmations and software filters reduce risk; they do not replace backups or make an operation reversible.

## Effects by action

| Action | Actual effect and risk |
| --- | --- |
| Capacity Test / re-verification | Creates deterministic test files in filesystem free space, flushes and reads them back. Normally removes generated files unless retention is selected. Writes can overwrite aliased existing data on counterfeit media, fill space, stress failing storage or leave files after interruption. |
| CHKDSK | Runs with `/F /R /X`: repairs filesystem metadata, scans for bad sectors and forces dismount where needed. This changes the filesystem and can affect damaged files; it is not a read-only diagnostic. |
| Format | Erases the selected volume's filesystem contents. Quick format is not secure erasure. |
| Delete partition | Removes the selected partition and access to its files. |
| Create partition | Changes disk layout in unallocated space. Confirm the physical disk and intended size. |
| Advanced Repair | Clears the read-only attribute, runs diskpart `clean`, creates a primary partition, marks it active, quick-formats and assigns a letter. It affects the entire selected physical disk, including its other volumes. |
| Fix Fake Drive | Deletes existing partitions, creates a smaller partition and formats it. Failure midway can leave an unpartitioned or unformatted device. |
| Assign Letter | Changes access paths; the legacy implementation selects partition 1 on the mapped physical disk. It can disrupt applications using the previous letter. |

These commands are not a secure data sanitization facility. There is no undo or transactional rollback.

## Different safety paths

`partition_utils.py` (USB Partitions and Fix Fake Drive) cross-checks Windows disk and WMI information, filters eligible removable USB flash devices, rejects boot/system or ambiguous identities, rechecks identity before destructive operations, and blocks protected partitions and read-only devices. It also scans diskpart output for known failures.

`usb_utils.py` (Repair Tools) enumerates removable logical drives and maps letters to disk numbers. Its legacy command wrappers do **not** share the same physical identity revalidation, protected-partition checks or diskpart failure-marker parsing. Format and Advanced Repair use a checkbox and confirmation dialog; CHKDSK and Assign Letter do not use that same two-stage confirmation. Do not assume every tab has identical protection, or that a zero process exit code proves every diskpart step succeeded.

Prefer the USB Partitions workflow for supported partition operations. Do not bypass a rejected device by switching to a weaker path.

## Capacity-test limitations

“Full capacity” tests available filesystem free space minus an 8 MiB reserve, rounded down to whole MiB. It does not test occupied files, unallocated space or every physical flash cell. Quick tests at most 1 GiB (the UI calls this “1 GB”); custom tests only the requested range. Displayed units use powers of 1024.

The engine uses `usbfix_test_*.bin` filenames. The UI offers cleanup of matching leftover files in the selected directory; inspect them before approving deletion and do not store your own files under that naming pattern. Cleanup is best effort. Stop through the UI and allow it to finish; do not unplug during writes or repair.

A PASS only means no errors were detected in the tested range during that run. A FAIL can result from faults, connection problems or fake capacity; it alone does not establish fraud. Fix Fake Drive uses an inferred contiguous usable boundary from a qualifying Full test and subtracts max(64 MiB, 1%), rounded down to MiB. This is a software partition-size workaround, not a controller firmware repair or reliability guarantee. Re-test afterwards and do not trust suspect storage with the only copy of data.

## Failures and privacy

After a partial repair failure, preserve the log, stop further operations and inspect the layout before deciding whether recovery or recreation is appropriate. Repeated formatting is not a recovery strategy.

HTML reports mask serial numbers and include a device fingerprint, model and test details. Logs, dialogs and screenshots may still reveal full identifiers and paths. Review and redact before sharing. Reports are locally generated statements, not independently verified or official/legal certificates.
