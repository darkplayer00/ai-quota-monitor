@echo off
title Instalador - AI Quota Widget
color 0b
echo ========================================================
echo       INSTALADOR OFICIAL - AI QUOTA WIDGET (AGY)
echo ========================================================
echo.
echo Instalando en tu sistema...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
echo ========================================================
echo   Instalacion completada con exito!
echo   Se ha creado un acceso directo en tu Escritorio y Menu Inicio.
echo ========================================================
echo.
pause
