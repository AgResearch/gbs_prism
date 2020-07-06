#!/bin/bash

FastqToTagCount_stdout=$1  # e.g. /dataset/gseq_processing/scratch/gbs/200626_D00390_0557_ACECFLANXX/SQ1345.all.cattle.PstI/200626_D00390_0557_ACECFLANXX.SQ1345.all.cattle.PstI.key.PstI.tassel3_qc.FastqToTagCount.stdout
HapMap_hmc=$2 # e.g. /dataset/gseq_processing/scratch/gbs/200626_D00390_0557_ACECFLANXX/SQ1345.all.cattle.PstI/hapMap/HapMap.hmc.txt

read_count=`grep "Total number of good barcoded reads" $FastqToTagCount_stdout | awk -F= '{print $2}' -`
snp_count=`wc -l $HapMap_hmc | awk '{print $1}' -`

#echo python -c "print '%8.6f%%'%round(100.0 * ( $snp_count - 1 ) / (1.0 * $read_count ),1)" 
percent=`python -c "print '(%7.3f%% of Total number of good barcoded reads)'%round(100.0 * ( $snp_count - 1 )/ (1.0 * $read_count ),3)" `

echo $snp_count $percent 
