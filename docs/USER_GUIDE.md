# USB Fix Tool — User Guide

This guide describes the desktop application's behavior as implemented in the repository. It does not guarantee the recovery of damaged data or the repair of defective hardware.

## 1. Before you start

1. Use **Windows 10/11** and connect the intended USB device directly, preferably without an unreliable hub.
2. Back up files before repair, formatting or partition operations. If a drive is physically failing, prioritize imaging/data recovery before further write operations.
3. Close applications that may be reading or writing the drive.
4. Launch the application from source or its one-folder executable; use **Run as administrator** when a repair or partition action needs elevation.
5. Confirm the drive **letter, label, capacity and physical disk identity**. If more than one storage device is connected and you cannot distinguish them, disconnect unnecessary devices first.

See [Safety and data loss](SAFETY.md) for details.

## 2. Capacity Test

**Purpose:** assess whether data written to a target can be read back correctly. The engine creates test files in available free space, writes deterministic data, flushes it, reads it back and compares it. A partial test cannot establish the capacity of untested regions.

1. Open **Capacity Test**, refresh the drive list and choose a writable target. The UI also accepts a selected folder; this does **not** make the folder's underlying storage eligible for physical-disk repair.
2. Choose a mode:
   - **Full capacity test:** test available free space, less the configured safety margin.
   - **Custom size test:** choose a specific size in MB or GB that fits the available test space.
   - **Quick verification:** test at most a 1 GiB sample; this is a limited sample, **not** a full-capacity conclusion.
3. Select **Start Test**. Watch the write and verification phases, progress, observed speeds, errors and log.
4. Read the result: **PASS**, **FAIL**, **STOPPED** or error. PASS means no mismatch was observed **within the tested range**, not a health guarantee for the entire USB controller or every byte on the device.
5. Use **Stop Test** if needed; stopping produces incomplete results and requests confirmation.

The application attempts to clean up its test files. If a prior test left files with the tool's test-file naming convention, the UI may offer to delete them. **Inspect any leftover files before agreeing to removal.** Do not store your own files under the application's test-file names.

### Fake-capacity proof and repair

When a **full** test fails with enough information to calculate a contiguous usable region, and the target maps to a positively identified, eligible removable USB flash disk, the UI may offer **Fix Fake Drive**. The proposed partition size is derived from observed usable space and includes a safety margin. It is **not** a firmware fix and cannot make counterfeit capacity real.

If **Export Proof Report** or **Copy Claim Text** becomes available, review the generated information before sending it to anyone. The HTML proof report is a locally generated technical account, not an independent laboratory or legal certification.

## 3. USB Partitions

**Purpose:** inspect and change the layout of an eligible removable USB flash drive. This tab applies stricter physical-device eligibility and re-verification checks than the general Repair Tools tab.

1. Open **USB Partitions**, press **Refresh**, and choose the target USB flash disk.
2. Inspect the partition list, allocated space, unallocated space, file systems and disk number.
3. Select the appropriate operation:
   - **Delete Partition:** permanently removes the selected non-protected partition and its accessible data.
   - **Create Partition:** creates a primary partition in unallocated space, using all available or a chosen size. A new partition generally needs formatting before use.
   - **Format Partition:** choose FAT32, exFAT or NTFS; choose quick or full formatting. The implementation prevents FAT32 formatting for partitions over 32 GB in this tab.
4. Read the confirmation and verify the **physical disk number, model, partition and size** before accepting.
5. Refresh and inspect the actual device layout after the operation; do not assume success from UI appearance alone.

System, EFI, Recovery and reserved partitions are treated as protected by the partition-management backend. Disk identity and removable-USB eligibility are rechecked ahead of destructive operations. These are defense-in-depth measures, not guarantees against user selection errors, driver issues or hardware faults.

### Fix Fake Drive and re-verification

Following a qualifying failed **Full** capacity test:

1. Select **Fix Fake Drive**, if offered.
2. Review the preview showing the verified disk, observed usable size, safety margin, proposed partition size and partitions to be removed.
3. Understand that the workflow **deletes the drive's existing partitions**, creates a smaller partition and formats it.
4. Only proceed if the data has been backed up and the physical device is unquestionably the intended one.
5. After a successful repair, use **Re-verify Repaired Drive** when offered. The UI performs another full write/read check of the repaired partition.
6. A successful re-verification can enable **Generate Verification Certificate**. It exports an HTML file that a browser can print to PDF.

A partially completed operation can leave a drive without a usable partition. Inspect the log and the refreshed partition layout before attempting recovery.

## 4. Repair Tools

**Purpose:** run Windows utilities against selected removable volumes or mapped disks.

- **Run CHKDSK:** invokes `chkdsk <drive>: /F /R /X`; this can modify the file system, dismount it and be slow. Back up or image a failing device first.
- **Format:** invokes the Windows `format` command with FAT32, exFAT or NTFS. The implementation uses quick formatting from this tab. **Existing data will be erased.**
- **Advanced Repair:** uses DiskPart to clear disk attributes, `clean` the selected physical disk, create a primary partition, format it and assign a letter. **This is disk-wide destructive operation.**
- **Assign Letter:** uses DiskPart to assign a letter to partition 1 on the mapped physical disk.

The **Format** and **Advanced Repair** actions require the UI checkbox and a confirmation dialog. Unlike `USB Partitions`, the `Repair Tools` implementation uses logical-drive enumeration and disk-number lookup rather than the same per-step removable-disk fingerprint checks. **Double-check the selection; do not rely on the app to make a destructive operation safe.**

## 5. Reports

The app saves reports as `.html` files. To obtain a PDF: open the saved file in a browser, choose **Print**, then **Save as PDF** if available. Reports contain a locally generated ID, masked serial number and device fingerprint. Share them only after reviewing their contents.

## 6. Troubleshooting

| Symptom | Suggested check |
| --- | --- |
| No drive appears | Reconnect it; check **Disk Management** and whether Windows recognizes the device; refresh in the app |
| Action requires administrator | Restart the application from an elevated terminal or use the executable's UAC prompt |
| Capacity test cannot start | Check target write access and free space; ensure no other test is running |
| Fix Fake Drive unavailable | Only a qualifying full failed test on a positively identified eligible flash drive can enable it |
| Disk operation reports an error | Read the application's log and inspect actual state in Disk Management; do not repeat destructive commands blindly |
| Drive is read-only | Check for a physical lock, system write protection or actual hardware faults |
| Re-verification fails | Treat the medium as unreliable; do not entrust it with important data |

If the drive disappears repeatedly, is making hardware error reports, or contains irreplaceable data, stop destructive attempts and seek specialized recovery assistance.
