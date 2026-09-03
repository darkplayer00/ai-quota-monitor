# Script de Instalacion para AI Quota Widget
$ErrorActionPreference = "Stop"

$AppName = "AI Quota Monitor"
$TargetDir = Join-Path $env:LOCALAPPDATA "Programs\AIQuotaWidget"
$DistExe = Join-Path $PSScriptRoot "dist\AI_Quota_Widget.exe"
$IconFile = Join-Path $PSScriptRoot "icon.ico"

Write-Host "-> Creando directorio de instalacion: $TargetDir" -ForegroundColor Cyan
if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# Cerrar cualquier instancia previa
Get-Process "AI_Quota_Widget" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-CimInstance Win32_Process -Filter "CommandLine like '%widget_app.py%'" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Milliseconds 500

Write-Host "-> Copiando binarios y recursos..." -ForegroundColor Cyan
Copy-Item $DistExe -Destination (Join-Path $TargetDir "AI_Quota_Widget.exe") -Force
Copy-Item $IconFile -Destination (Join-Path $TargetDir "icon.ico") -Force

# Crear accesos directos
$WshShell = New-Object -ComObject WScript.Shell

# 1. Acceso directo en el Escritorio
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = $WshShell.CreateShortcut((Join-Path $DesktopPath "$AppName.lnk"))
$DesktopShortcut.TargetPath = Join-Path $TargetDir "AI_Quota_Widget.exe"
$DesktopShortcut.WorkingDirectory = $TargetDir
$DesktopShortcut.IconLocation = (Join-Path $TargetDir "icon.ico") + ",0"
$DesktopShortcut.Description = "Monitor de Cuota AI en Tiempo Real"
$DesktopShortcut.Save()
Write-Host "-> Acceso directo en el Escritorio creado." -ForegroundColor Green

# 2. Acceso directo en el Menu Inicio
$StartMenuPath = [Environment]::GetFolderPath("Programs")
$StartShortcut = $WshShell.CreateShortcut((Join-Path $StartMenuPath "$AppName.lnk"))
$StartShortcut.TargetPath = Join-Path $TargetDir "AI_Quota_Widget.exe"
$StartShortcut.WorkingDirectory = $TargetDir
$StartShortcut.IconLocation = (Join-Path $TargetDir "icon.ico") + ",0"
$StartShortcut.Description = "Monitor de Cuota AI en Tiempo Real"
$StartShortcut.Save()
Write-Host "-> Acceso directo en Menu Inicio creado." -ForegroundColor Green

# 3. Crear script de Desinstalacion
$UninstallerPath = Join-Path $TargetDir "Desinstalar.bat"
$UninstContent = @"
@echo off
title Desinstalador - AI Quota Widget
color 0c
echo ===================================================
echo             DESINSTALADOR - AI QUOTA WIDGET
echo ===================================================
echo.
echo Cerrando procesos en ejecucion...
taskkill /F /IM AI_Quota_Widget.exe >nul 2>&1
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq AI Quota*" >nul 2>&1

echo Eliminando accesos directos...
del "%USERPROFILE%\Desktop\AI Quota Monitor.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\AI Quota Monitor.lnk" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AI_Quota_Widget.vbs" >nul 2>&1

echo Eliminando configuracion...
rd /s /q "%APPDATA%\AIQuotaWidget" >nul 2>&1

echo.
echo Desinstalacion completada. Puedes borrar la carpeta de instalacion si lo deseas.
echo.
pause
"@
Set-Content -Path $UninstallerPath -Value $UninstContent -Encoding UTF8
Write-Host "-> Desinstalador configurado en: $UninstallerPath" -ForegroundColor Green

# 4. Iniciar la aplicacion recien instalada
Write-Host "-> Iniciando $AppName..." -ForegroundColor Cyan
Start-Process (Join-Path $TargetDir "AI_Quota_Widget.exe") -WorkingDirectory $TargetDir

Write-Host "-> Proceso finalizado con exito!" -ForegroundColor Green
