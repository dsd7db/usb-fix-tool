# Safety, destructive operations and limitations

**Important:** This repository contains a utility that can issue irreversible Windows disk-management commands. Incorrect physical-disk selection or unexpected Windows/device behavior can destroy data. Use only on devices you own or are authorized to administer.

## Operation risk overview

| Operation | Typical impact | Data risk |
| --- | --- | --- |
| Capacity Test | Creates large temporary test files on available free space, writes and reads them; attempts cleanup | Writes to the device; can stress failing media; unintended cleanup of matching leftover filenames is possible |
| CHKDSK `/F /R /X` | Repairs file-system structures, scans for unreadable sectors and dismounts the volume | Can modify metadata and can aggravate a failing drive |
| Assign drive letter | Alters volume access path via DiskPart | Usually non-erasing, but targets must still be verified |
| Delete partition | Removes selected partition | **Destructive — data may become inaccessible** |
| Create partition | Changes partition table | Changes device layout; inappropriate use can complicate recovery |
| Format (quick/full) | Recreates file-system structures | **Destructive — files on the formatted volume will be lost** |
| Advanced Repair | DiskPart `clean`, partition creation and formatting | **Disk-wide destructive** |
| Fix Fake Drive | Deletes existing partitions, creates a smaller partition and formats it | **Disk-wide destructive** |

## Identity and protection boundaries

- `USB Partitions` uses the `partition_utils.py` backend to enumerate candidate flash drives, exclude ineligible devices and revalidate disk number, model, capacity, and hardware identifiers before destructive actions. It blocks protected partition types and detected read-only devices.
- The **Fix Fake Drive** workflow uses those partition backend checks and aborts on certain inconsistencies or partial failures. A partial operation can still leave the drive without its former layout.
- `Repair Tools` is implemented separately through `usb_utils.py`. Its logical-drive selection and physical-disk lookup are **not equivalent** to the identity gates used in `USB Partitions`. Do not assume system disks are impossible to target under all circumstances.
- GUI prompts and disk identities can be stale or misleading if USB devices are removed, reinserted or reassigned. Safeguards reduce risk but **cannot eliminate** it.

## Minimum safe procedure

1. Back up or image valuable files **before** any repair or test that writes to the storage medium.
2. Disconnect unrelated removable storage and any backup disk you do not want to touch.
3. Verify the target's physical disk number and capacity using **Windows Disk Management** and, if needed, PowerShell `Get-Disk` or `Get-Partition`.
4. Run a non-destructive inspection first and read the log.
5. Do **not** proceed with Format, Delete, Advanced Repair, or Fix Fake Drive if you cannot confidently identify the exact physical device.
6. Recheck target selection immediately before confirming an operation.
7. After any operation, refresh the device information and verify the outcome independently.

## What the capacity test can and cannot establish

- A **full test** only covers the available free space targeted during that run, not necessarily every block of a disk already containing files.
- A **quick or custom test** covers only the tested sample and cannot establish that untested capacity is genuine.
- Results reflect measured read/write behavior at test time; they are not a warranty, manufacturer certification or proof of long-term retention.
- Generated HTML reports are local technical artifacts, **not independent or legal certifications**.

## Recovery and emergencies

If you select the wrong disk or lose access to data, **stop writing immediately**. Additional formatting, repeated repair commands, or another write test can reduce the chance of recovery. Do not attempt a fake-capacity reduction on a drive whose contents you need to recover first.

The repository also includes a static marketing website with placeholder download links and other publication-stage claims. Those are **not evidence that a verified installation package or service is available**.
