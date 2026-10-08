@echo off
setlocal EnableExtensions
REM ===================================================================
REM  Build Coretax Faktur (coretax_faktur_gui.py) -> folder + ZIP siap kirim
REM  Pemakaian:
REM    build.bat            build biasa
REM    build.bat source     PyInstaller dengan bootloader dikompilasi sendiri
REM                         (lebih jarang ditandai antivirus; perlu
REM                          "Visual Studio Build Tools" - C++ workload)
REM  Tanda tangan digital (opsional): set variabel sebelum menjalankan
REM    set SIGN_PFX=C:\path\sertifikat.pfx
REM    set SIGN_PASS=passwordnya
REM ===================================================================

set APP=CoretaxFaktur
set SRC=coretax_faktur_gui.py
set VENV=.venv-build

cd /d "%~dp0"
if not exist "%SRC%" (echo [X] %SRC% tidak ditemukan di folder ini. & goto :fail)
if not exist "core.py" (echo [X] core.py tidak ditemukan - harus satu folder dengan %SRC%. & goto :fail)

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo [X] Python belum terpasang. & goto :fail)

echo.
echo [1/5] Menyiapkan virtualenv bersih (%VENV%)...
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%" || goto :fail
set VPY=%VENV%\Scripts\python.exe
"%VPY%" -m pip install --upgrade pip wheel setuptools -q || goto :fail
"%VPY%" -m pip install requests openpyxl cryptography -q || goto :fail

echo [2/5] Memasang PyInstaller...
if /i "%~1"=="source" (
    echo     - mode source: bootloader dikompilasi ulang, butuh waktu beberapa menit
    "%VPY%" -m pip uninstall -y pyinstaller >nul 2>nul
    "%VPY%" -m pip install --no-binary pyinstaller --no-cache-dir pyinstaller || (
        echo [X] Gagal kompilasi bootloader. Pasang Visual Studio Build Tools ^(C++^) atau jalankan tanpa "source".
        goto :fail)
) else (
    "%VPY%" -m pip install --upgrade pyinstaller -q || goto :fail
)

echo [3/5] Build (onedir, tanpa UPX, dengan version info)...
set ICON=
if exist "app.ico" set ICON=--icon app.ico
rmdir /s /q build "dist\%APP%" 2>nul
"%VPY%" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx ^
    --name "%APP%" --version-file version_info.txt %ICON% ^
    --hidden-import cryptography.hazmat.primitives.asymmetric.ed25519 ^
    "%SRC%" || goto :fail

echo [4/5] Tanda tangan digital...
if defined SIGN_PFX (
    where signtool >nul 2>nul || (echo     - signtool tidak ditemukan ^(Windows SDK^), dilewati & goto :zip)
    signtool sign /f "%SIGN_PFX%" /p "%SIGN_PASS%" /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "dist\%APP%\%APP%.exe" || goto :fail
) else (
    echo     - SIGN_PFX tidak di-set, dilewati
)

:zip
echo [5/5] Membuat ZIP...
copy /y "BACA_DULU.txt" "dist\%APP%\" >nul 2>nul
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set TGL=%%d
set ZIP=dist\%APP%_%TGL%.zip
del /q "%ZIP%" 2>nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\%APP%' -DestinationPath '%ZIP%' -Force" || goto :fail

echo.
echo  Selesai.
echo    Folder : dist\%APP%\%APP%.exe
echo    Kirim  : %ZIP%
echo.
pause
exit /b 0

:fail
echo.
echo  BUILD GAGAL - lihat pesan di atas.
pause
exit /b 1
