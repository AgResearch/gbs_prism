#!/bin/bash

set -x
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms


if [ -z "$2" ]; then
   echo "example: ./sample_tags_sorted.sh /dataset/gseq_processing/scratch/gbs/180824_D00390_0394_BCCPYFANXX/SQ0783.all.DEER.PstI/tagCounts/qc297624-1_CCPYFANXX_2_783_X4.cnt  /dataset/gseq_processing/scratch/gbs/180824_D00390_0394_BCCPYFANXX/SQ0783.all.DEER.PstI/annotation 
   exit 1
fi

if [ ! -f $1 ]; then
   echo "no such input $1"
   exit 1
fi

if [ ! -d $2 ]; then
   echo "no such output $2"
   exit 1
fi


sample_tag_file=$1
base=`basename $sample_tag_file`

conda activate tassel3

$SEQ_PRISMS_BIN/cat_tag_count.sh $sample_tag_file | sort -n -k3,3 > $2/$base.tagcount

set +x
