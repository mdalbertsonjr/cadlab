#!/bin/bash

mkdir -p $HOME/.local/bin
mkdir -p $HOME/.local/lib/node_modules
mkdir -p $HOME/.local/lib/pi-coding-agent
echo export PATH=$HOME/.local/bin/:$PATH >> $HOME/.bashrc
echo export NODE_PATH=$HOME/.local/lib/node_modules:$NODE_PATH >> $HOME/.bashrc
cd $HOME/.local/lib/pi-coding-agent
npm install @earendil-works/pi-coding-agent
