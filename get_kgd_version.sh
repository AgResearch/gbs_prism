#!/bin/bash

if [ -z "$GBS_PRISM_BIN" ]; then
   echo "error GBS_PRISM_BIN not set"
   exit 1
fi

cd $GBS_PRISM_BIN/KGD

git describe --tags
