#!/bin/bash
clear
  python build.py
time bash -c '
  ./main
  echo "Exit code: $?"
'