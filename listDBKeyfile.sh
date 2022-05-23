#!/bin/bash

OUR_PYTHON=/usr/bin/python2.7

export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms

$OUR_PYTHON $GBS_PRISM_BIN/list_keyfile_stub.py "$@"
