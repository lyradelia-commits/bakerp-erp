@echo off
setlocal enabledelayedexpansion
title BakeERP (MySQL) - Roti Kita Bakery
cd /d "%~dp0"

set "MYSQLD=C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqld.exe"
set "MYINI=C:\laragon\bin\mysql\mysql-8.0.30-winx64\my.ini"

echo ============================================================
echo   BakeERP - Mode MySQL
echo ============================================================
echo.

set "CEK3306=powershell -NoProfile -Command \"try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',3306);$c.Close();exit 0}catch{exit 1}\""
set "CEK8000=powershell -NoProfile -Command \"try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8000);$c.Close();exit 0}catch{exit 1}\""

REM ---- 1. Pastikan server MySQL hidup ----
%CEK3306% >nul 2>&1
if %errorlevel%==0 (
    echo [1/2] Server MySQL sudah berjalan di port 3306.
) else (
    echo [1/2] Menyalakan server MySQL...
    if not exist "%MYSQLD%" (
        echo.
        echo [GAGAL] MySQL tidak ditemukan di:
        echo   %MYSQLD%
        echo Jalankan lewat Laragon, atau install MySQL terlebih dahulu.
        pause
        exit /b 1
    )
    start "MySQL Server" /min "%MYSQLD%" --defaults-file="%MYINI%" --standalone
    set /a n=0
    :waitmysql
    ping -n 2 127.0.0.1 >nul
    set /a n+=1
    %CEK3306% >nul 2>&1
    if %errorlevel%==0 goto mysqlok
    if !n! lss 30 goto waitmysql
    echo [GAGAL] MySQL tidak merespons dalam 30 detik.
    pause
    exit /b 1
    :mysqlok
    echo       MySQL siap.
)

REM ---- 2. Jalankan aplikasi dengan backend MySQL ----
REM Cek dulu: apakah port 8000 sudah dipakai, dan backend-nya apa?
set "CEKINFO=powershell -NoProfile -Command \"try{$r=Invoke-RestMethod 'http://127.0.0.1:8000/api/info' -TimeoutSec 3; if(\$r.data.backend -eq 'mysql'){exit 0}else{exit 1}}catch{exit 2}\""

%CEKINFO% >nul 2>&1
set "INFO=%errorlevel%"

if "%INFO%"=="0" (
    echo [2/2] Aplikasi sudah berjalan dalam mode MySQL. Membuka browser...
    start "" "http://localhost:8000"
    ping -n 4 127.0.0.1 >nul
    exit /b 0
)

if "%INFO%"=="1" (
    echo [2/2] Ditemukan BakeERP mode SQLite di port 8000. Menghentikannya...
    powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force }" >nul 2>&1
    ping -n 4 127.0.0.1 >nul
    echo       Port 8000 dibebaskan.
)

if "%INFO%"=="2" (
    REM Port 8000 mungkin dipakai proses lain (atau BakeERP versi lama). Bebaskan bila perlu.
    %CEK8000% >nul 2>&1
    if !errorlevel!==0 (
        echo [2/2] Port 8000 sedang dipakai. Menghentikan proses tersebut...
        powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force }" >nul 2>&1
        ping -n 4 127.0.0.1 >nul
    )
)

echo [2/2] Menjalankan BakeERP dengan backend MySQL...
start "BakeERP Server (MySQL)" cmd /k "set BAKERP_BACKEND=mysql&& python app.py"

set /a n=0
:waitapp
ping -n 2 127.0.0.1 >nul
set /a n+=1
%CEK8000% >nul 2>&1
if %errorlevel%==0 goto appok
if !n! lss 30 goto waitapp
echo [GAGAL] Aplikasi tidak merespons. Periksa jendela "BakeERP Server (MySQL)".
pause
exit /b 1

:appok
start "" "http://localhost:8000"
echo.
echo ============================================================
echo   Aplikasi terbuka: http://localhost:8000
echo   Login demo: admin / admin123
echo.
echo   Basis data: MySQL 127.0.0.1:3306 / database "bakerp"
echo   Lihat isinya lewat DBeaver atau MySQL Workbench:
echo     host=127.0.0.1  port=3306  user=root  password=(kosong)
echo.
echo   Jendela "BakeERP Server (MySQL)" harus tetap terbuka.
echo ============================================================
ping -n 7 127.0.0.1 >nul
exit /b 0
