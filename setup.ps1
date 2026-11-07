# One-time setup on Windows (PowerShell): creates .venv on Python 3.11 and installs pinned deps.
#   powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv venv --python 3.11 .venv
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    uv pip install --python .venv\Scripts\python.exe --no-deps -r requirements-nodeps.txt
} else {
    py -3.11 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m pip install --no-deps -r requirements-nodeps.txt
}
Write-Host "Done. Activate with: .venv\Scripts\Activate.ps1"
