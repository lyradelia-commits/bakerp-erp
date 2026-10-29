@echo off
setlocal
title BakeERP - Roti Kita Bakery
cd /d "%~dp0"

echo ============================================================
echo   BakeERP - Sistem ERP Bakery
echo ============================================================
echo.

REM Cek apakah port 8000 sudah melayani koneksi
set "CEK=powershell -NoProfile -Command \"try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8000);$c.Close();exit 0}catch{exit 1}\""

%CEK% >nul 2>&1
if %errorlevel%==0 (
    echo Server sudah berjalan. Membuka browser...
    start "" "http://localhost:8000"
    ping -n 4 127.0.0.1 >nul
    exit /b 0
)

echo Menjalankan server...
start "BakeERP Server" cmd /k "python app.py"
echo Menunggu server siap...

REM Tunggu sampai port benar-benar menerima koneksi (maks +/- 25 detik)
set /a n=0
:waitloop
ping -n 2 127.0.0.1 >nul
set /a n+=1
%CEK% >nul 2>&1
if %errorlevel%==0 goto ready
if %n% lss 25 goto waitloop

echo.
echo [GAGAL] Server tidak merespons. Pastikan Python terpasang.
echo Coba jalankan manual:  python app.py
pause
exit /b 1

:ready
echo Server siap. Membuka browser...
start "" "http://localhost:8000"
echo.
echo ============================================================
echo   Aplikasi terbuka di browser: http://localhost:8000
echo   Login: admin / admin123
echo.
echo   Jangan tutup jendela "BakeERP Server" selama memakai
echo   aplikasi. Untuk menghentikan server, tutup jendela itu.
echo ============================================================
ping -n 7 127.0.0.1 >nul
exit /b 0
