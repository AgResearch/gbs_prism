#!/bin/bash

set -x
export GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
export SEQ_PRISMS_BIN=/dataset/gseq_processing/active/bin/gbs_prism/seq_prisms


if [ -z "$2" ]; then
   echo "example: ./annotate_sample_lowdepth.sh /dataset/gseq_processing/scratch/gbs/180921_D00390_0400_BCCVDJANXX/SQ0799.all.DEER.PstI/fasta_medium_lowdepthsample/qc304501-1_CCVDJANXX_2_799_X4.cnt.tag_count_unique.s.05m2T10_taggt2.fasta /dataset/gseq_processing/scratch/gbs/180921_D00390_0400_BCCVDJANXX/SQ0799.all.DEER.PstI/annotation"
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


sample_fasta=$1
output_folder=$2

cd $output_folder/..   # attempt to use relevant run time e.g. tardis.toml

#time $SEQ_PRISMS_BIN/align_prism.sh -f -a blastn  -r nt  -p "-evalue 1.0e-10  -dust \'20 64 1\'  -outfmt \'7 qseqid sseqid pident evalue staxids sscinames scomnames sskingdoms stitle\'"  -O $output_folder $sample_fasta 

base=`basename $sample_fasta .fasta`
moniker=`echo $base | awk -F_ '{print $1}' -`
$SEQ_PRISMS_BIN/taxonomy_prism.py  --column_numbers 0,3,7,6  --summary_type dump_top_hits --top_hit_selection_method best $output_folder/$moniker*.results.gz > $output_folder/${moniker}.best_hits.txt 


# example further summary:
#cat /dataset/gseq_processing/scratch/gbs/181005_D00390_0407_BCCV91ANXX/SQ0807.all.PstI.PstI/annotation/qc314325-1.best_hits.txt | grep -v "No hits" | awk -F, '{print $4}' -  | sort | uniq -c | sort -n -k 1,1
