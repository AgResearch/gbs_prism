#!/bin/sh

if [ -z "$1" ]; then
   echo "usage :
      ./summarise_bwa_mappings.sh run_name  working folder
      e.g.
      ./summarise_bwa_mappings.sh 170207_D00390_0282_ACA7WHANXX /dataset/hiseq/scratch/postprocessing/170207_D00390_0282_ACA7WHANXX.processed/mapping_preview
      "
   exit 1
fi

RUN=$1
WORKING_FOLDER=$2
DRY_RUN=$3

if [ -z "$DRY_RUN" ]; then
   DRY_RUN="no"
elif [[ $DRY_RUN == "y" || $DRY_RUN == "Y" || $DRY_RUN == "yes" ]]; then
   DRY_RUN="yes"
else
   DRY_RUN="no"
fi

BCL2FASTQ_FOLDER=${WORKING_FOLDER}/../bcl2fastq/
PARAMETERS_FILE=${WORKING_FOLDER}/../../${RUN}.SampleProcessing.json
RUN_ROOT=${WORKING_FOLDER}/..

if [ ! -d ${WORKING_FOLDER} ]; then
   echo "error ${WORKING_FOLDER} is missing"
   exit 1
fi

if [ ! -f $PARAMETERS_FILE ]; then
   echo "$PARAMETERS_FILE missing - please run get_processing_parameters.py (for help , ./get_processing_parameters.py -h)"
   exit 1
fi

# for each sample , the mapping preview folder contains files like 
# Repro.sample.fastq.trimmed_vs_umd_3_1_reference_1000_bull_genomes.fa
# - i.e. sample.etc.etc.stats 
# These contain : (e.g)
#
#Mapped reads:      260087	(70.3575%)
#Forward strand:    239494	(64.7868%)
#Reverse strand:    130171	(35.2132%)
# these are what we need for the three summaries 

$SEQ_PRISMS_BIN/collate_mapping_stats.py $WORKING_FOLDER/*.stats > $WORKING_FOLDER/stats_summary.txt
Rscript --vanilla  $SEQ_PRISMS_BIN/mapping_stats_plots.r datafolder=$WORKING_FOLDER 


echo "*** summarise_bwa_mappings.sh has completed ***"

exit 0
