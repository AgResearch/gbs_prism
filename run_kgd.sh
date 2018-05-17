#!/bin/sh
#
# stub for running KGD. It takes one argument
# 1. The KGD folder - this will be working folder
#    e.g. /dataset/hiseq/scratch/postprocessing/151113_D00390_0239_BC808AANXX.gbs/SQ0139.processed_sample/uneak/KGD
# so e.g. run as 
# run_kgd.sh /dataset/hiseq/scratch/postprocessing/151113_D00390_0239_BC808AANXX.gbs/SQ0139.processed_sample/uneak/KGD
KGD_WORKING=$1
HAPMAP_DATA=`dirname $KGD_WORKING`
HAPMAP_DATA=${HAPMAP_DATA}/hapMap/HapMap.hmc.txt

cd $KGD_WORKING
Rscript --vanilla ../run_kgd.R $HAPMAP_DATA  
