**English** | [Español](README.es.md) | [中文](README.zh.md)

# SuperChis Auto-Production Tool

Desktop app (Python + PySide6) for mass-producing Game Boy Advance cartridges with SuperChis flash programmers.

## Features

### 1. Multi-device management
- ✅ Automatically scans and detects SuperChis programmers over USB
- ✅ Connect several devices at the same time
- ✅ Live status indicator (connected / disconnected / busy)
- ✅ Batch connect/disconnect
- ✅ Per-device control

### 2. Automatic quality check
- ✅ **SDRAM read/write test**
- ✅ **SRAM read/write test** (bank switching and full 128KB test)
- ✅ **Flash erase / blank check** – erases automatically if the Flash is not empty
- ✅ **Flash PPB unlock** – checks and clears the PPB protection bits

### 3. Automatic production
- ✅ Choose the ROM file (`.gba`)
- ✅ Compares the first 4K of the Flash and writes only when the data differs
- ✅ Automatic sector erase
- ✅ Buffer Write for faster programming
- ✅ Automatic verification of the written data
- ✅ Live progress per device

### 4. User interface
- ✅ Device list with an independent progress bar per device
- ✅ Real-time log output
- ✅ Batch operations
- ✅ Language selector at startup (中文 / Español)

## Installation

Requires Python 3.9+ (3.12 or 3.13 recommended).

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python chismaker.py
```

On startup you can choose the interface language and optionally remember it. To skip the dialog use `--lang es` or `--lang zh`. The "Language" button in the left panel resets the saved choice (restart to apply).

1. **Connect devices** – the app scans USB ports and lists SuperChis devices. Click "Connect all" or connect each one individually.
2. **Quality check (optional but recommended)** – run the batch check or check one device, and make sure every item passes.
3. **Production** – pick a `.gba` file, then run the batch production or produce a single device.
4. **Monitor** – each device has its own progress bar; the log shows the details.

## Building standalone executables

```bash
pip install pyinstaller
pyinstaller --noconfirm chismaker.spec
```

Run it on each target OS (PyInstaller does not cross-compile): `.exe` on Windows, `.app` on macOS.

## Technical details

### `device_adapter.py` functions
- `readRomID()` – read the Flash chip ID
- `getRomCFI()` – CFI information (capacity, sector size, …)
- `getRomEraseTime()` – erase timeouts
- `eraseChip()` / `eraseSector()` – chip and sector erase
- `programRom()` – ROM programming (with Buffer Write)
- `unlockPPB()` / `checkPPBLocked()` – PPB protection
- `verifyRom()` – data verification

### SuperChis unlock mechanism
Unlocked through a magic address:
- Magic address: `0x01FFFFFE` (GBA address space)
- Magic value: `0xA55A`
- Flash mapping value: `0xA558`

Configuration bits:
- Bit 0: SDRAM / Flash switch
- Bit 1: SD card enable
- Bit 2: write enable
- Bit 3: SRAM bank select

### Threading model
- `DeviceScanner` – background device scanning
- `QualityCheckWorker` – quality check
- `ProductionWorker` – production

Each device runs in its own thread, so operations do not interfere with each other.

## Troubleshooting

- **Device not detected:** check the USB cable, confirm the VID:PID is `0x0483:0x0721`, replug the device.
- **Quality check fails:** SDRAM → check hardware connections; SRAM → check the SRAM chip; Flash erase → try unlocking the PPB manually; PPB unlock → check the Flash chip model.
- **Production fails:** make sure the quality check passed, verify the ROM file, and read the detailed log.

## Supported Flash chips

CFI-compatible chips, including S29GL256 (Spansion), JS28F256 (Intel), S29GL01 (Spansion), S70GL02 (Spansion), MX29GL256 (Macronix) and M29W256G (Micron).

## Roadmap

- [ ] GBC cartridge support
- [ ] Save backup / restore
- [ ] Automatic cartridge identification
- [ ] Production statistics report
- [ ] Save / load configuration

## License

MIT License

## Credits

Protocol implementation based on the ChisFlashBurner project.
