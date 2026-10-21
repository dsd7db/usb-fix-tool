# Installation and build

## Desktop prerequisites

Use Windows with Python 3.10+ and pip/venv support. The batch build requires the `py` launcher. Windows operations use PowerShell, Windows storage cmdlets/WMI, CHKDSK, format and diskpart. Repair and partition changes require administrator privileges. The repository does not establish a tested Windows-version/CPU-architecture matrix.

The desktop requirement is exactly `PySide6>=6.6,<7.0`. Choose a Python version supported by the resolved PySide6 distribution; “3.10+” is not a guarantee for every future Python release.

Clone and enter the desktop folder from Command Prompt:

```bat
git clone https://github.com/dsd7db/usb-fix-tool.git
cd usb-fix-tool\usb-fix-tool\desktop
```

### Launcher

```bat
run.bat
```

It creates `.venv` if needed, upgrades pip, installs requirements and starts `main.py` with pythonw. It does not automatically elevate. For repair operations, open an administrator Command Prompt, enter this folder and launch there. For visible startup errors, use the manual command below.

### Manual source setup

From the desktop directory:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

No environment variables, database or web server are required for the desktop app. The recovery footer opens the placeholder URL in `main.py`'s `AFFILIATE_URL`; it is not integrated file recovery.

### Build a Windows executable

From the desktop directory on Windows:

```bat
build.bat
```

The script creates/uses `.venv`, upgrades pip, installs desktop requirements plus unpinned `pyinstaller`, then runs `pyinstaller --noconfirm build.spec`.

Output: `usb-fix-tool/desktop/dist/USBFixTool/USBFixTool.exe` relative to the repository root. Distribute the **entire** `USBFixTool` folder with its dependencies. The spec bundles assets, disables UPX, uses a windowed folder build and requests administrator privileges through UAC. It does not configure code signing.

PyInstaller and PySide6 are not fully pinned; the spec contains tool-version-sensitive options. These are the repository's build instructions, not a claim that every current dependency combination builds successfully. Record resolved versions and complete a Windows build/smoke check before distributing a binary. Do not bypass antivirus protection based on documentation claims.

## Desktop regression scripts

These are standalone Python scripts, not a conventional pytest-only suite. The checked-in scripts hard-code imports from `/app/usb-fix-tool/desktop`; several also write and recursively remove fixed `/tmp/st_*` directories. The Bash runner sets Qt offscreen and uses Unix `timeout`. They are not directly portable Windows test commands.

Use an isolated disposable development environment with the checkout mounted at `/app`, Python/PySide6 installed and no valuable files in the fixed scratch locations. Review every script before running. From `/app/usb-fix-tool/desktop` in that environment:

```sh
bash tests/run_all.sh
```

A focused engine check in the same environment is:

```sh
python tests/test_engine.py
```

Do not run these scripts against a shared scratch directory containing other data. Relevant backend tests mock Windows commands, but passing them does not establish real-device safety or successful Windows packaging. Use only disposable, backed-up media for any explicitly planned hardware validation. No test run is claimed by this documentation change.

## Static website

`usb-fix-tool/website/` contains plain HTML/CSS/JavaScript. There is no compilation step or package manifest there. For a local preview from the repository root:

```bat
py -3 -m http.server 8080 --bind 127.0.0.1 --directory usb-fix-tool/website
```

Open http://127.0.0.1:8080. Review download links, placeholder domains and marketing claims before publishing; the presence of a download page does not establish an available executable release.

## Separate React/FastAPI starter

This is optional development scaffolding, not a desktop runtime or USB-control API.

### Backend

From the repository root in Command Prompt, with a separately installed/running local MongoDB:

```bat
py -3 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
set MONGO_URL=mongodb://127.0.0.1:27017
set DB_NAME=usb_fix_tool_dev
set CORS_ORIGINS=http://localhost:3000
backend\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

`MONGO_URL` and `DB_NAME` are required at import; `backend/.env` is also loaded. CORS defaults to `*`; set explicit local origins. Implemented routes are GET `/api/`, POST `/api/status` with JSON `{"client_name":"example"}`, and GET `/api/status` (up to 1000 records). There is no authentication in these routes; do not expose this starter service publicly as-is. The broad requirements file contains packages beyond the imports used here, including an external integration package whose availability is not established by this guide.

### Frontend

`frontend/package.json` declares Yarn 1.22.22. Install Node.js and that Yarn version separately; the repository does not pin a Node version or include a lockfile. From the repository root:

```bat
cd frontend
yarn install
set REACT_APP_BACKEND_URL=http://127.0.0.1:8000
yarn start
```

In another terminal, from `frontend/`:

```bat
yarn build
```

The scripts invoke CRACO and emit the usual `frontend/build/` static output. The backend URL is embedded at build time, so set it in the build terminal too if needed. The current page requests the greeting and displays a starter screen; it provides no USB controls.

Dependency compatibility is not validated here: React 19 is declared alongside react-day-picker 8.10.1, and a development package is fetched from an external tarball. If resolution fails, capture the error for a separate dependency fix rather than forcing peer-dependency overrides. No successful web install/build is claimed.
