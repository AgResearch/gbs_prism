#!/bin/sh
#
# stub for running GUSbase. It takes one argument 
# 1. The KGD folder - this will be working folder
#    e.g. /dataset/gseq_processing/scratch/gbs/201030_D00390_0583_ACD658ANXX/SQ1465.all.goat.PstI/KGD 

KGD_WORKING=$1
cd $KGD_WORKING

if [ ! -f GUSbase.RData ]; then
   echo "*** could not see GUSbase.RData in $KGD_WORKING so not running GUSbase ***"
   exit 0  # don't regard this as an error (at the moment)
fi

source /stash/miniconda3/etc/profile.d/conda.sh
conda activate $GBS_PRISM_BIN/conda/GUSbase

Rscript --vanilla ../run_GUSbase.R GUSbase.RData  

if [ -f Rplots.pdf ]; then
   mv Rplots.pdf GUSbase_comet.pdf
   convert GUSbase_comet.pdf GUSbase_comet.jpg
fi
