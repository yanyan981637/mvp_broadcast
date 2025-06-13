#!/bin/bash
cd "$(dirname "$0")"
python3 live_broadcast_keyword.py
read -n 1 -s -r -p "Press any key to continue"
echo
