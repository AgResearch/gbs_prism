#!/bin/sh
#
# stub for running KGD. It takes two required arguments and 1 optional argument
# 1. The KGD folder - this will be working folder
#    e.g. /dataset/hiseq/scratch/postprocessing/151113_D00390_0239_BC808AANXX.gbs/SQ0139.processed_sample/uneak/KGD
# 2. The "geno_method" (prev called samptype)  , "default" or "pooled" (default for diploid)
# 3. Optional hapMap folder name (e.g. if want to use filtered hapMap data)
# so e.g. run as 
# run_kgd.sh /dataset/hiseq/scratch/postprocessing/151113_D00390_0239_BC808AANXX.gbs/SQ0139.processed_sample/uneak/KGD diploid
# or (non-default mapMap folder)
# run_kgd.sh /dataset/hiseq/scratch/postprocessing/151113_D00390_0239_BC808AANXX.gbs/SQ0139.processed_sample/uneak/KGD diploid filtered_hapMap

KGD_WORKING=$1
KGD_METHOD=$2
optional_hapmap_arg="$3"

hapmap_folder=hapMap
if [ ! -z "$optional_hapmap_arg" ]; then
   hapmap_folder=$optional_hapmap_arg
fi

HAPMAP_DATA=`dirname $KGD_WORKING`
HAPMAP_DATA=${HAPMAP_DATA}/${hapmap_folder}/HapMap.hmc.txt

if [ -f ${HAPMAP_DATA}.blinded ]; then
   HAPMAP_DATA=${HAPMAP_DATA}.blinded
fi

cd $KGD_WORKING
R_version=`Rscript --version 2>&1`
echo "(running $R_version)"
Rscript --vanilla ../run_kgd.R $HAPMAP_DATA  $KGD_METHOD  
