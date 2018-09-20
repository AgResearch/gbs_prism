#!/bin/bash

# compatability wrapper 
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms

$GBS_PRISM_BIN/list_keyfile.sh "$@"

