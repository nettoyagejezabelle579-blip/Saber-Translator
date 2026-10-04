@echo off
chcp 65001 >nul
title Saber-Translator Update
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update-Saber.ps1"
echo.
pause
