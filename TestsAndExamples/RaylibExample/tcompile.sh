#!/bin/bash
clear

python BHUMI.py main.bhumi -o main.ll &&

opt -O2 main.ll -o main.opt.ll &&

clang -O2 -Wno-override-module main.opt.ll stdlib.c \
  -I./raylib-5.5_linux_amd64/include \
  ./raylib-5.5_linux_amd64/lib/libraylib.a \
  -lGL -lm -lpthread -ldl -lrt -lX11 \
  -o main &&

time bash -c './main; echo "Exit code: $?"'
