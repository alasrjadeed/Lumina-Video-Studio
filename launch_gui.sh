#!/bin/bash
# Lumina Video Studio - Server Manager GUI Launcher
# Double-click or run from terminal to open the server manager

cd "/home/oem/Documents/Lumina Video Studio"

# Use system Python (has customtkinter)
exec python3 server_gui.py "$@"
