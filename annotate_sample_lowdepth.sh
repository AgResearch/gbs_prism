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
# example : /dataset/gseq_processing/scratch/gbs/180921_D00390_0400_BCCVDJANXX/SQ0799.all.DEER.PstI/fasta_medium_lowdepthsample/qc304501-1_CCVDJANXX_2_799_X4.cnt.tag_count_unique.s.05m2T10_taggt2.fasta
output_folder=$2
#example : /dataset/gseq_processing/scratch/gbs/180921_D00390_0400_BCCVDJANXX/SQ0799.all.DEER.PstI/annotation

cd $output_folder/..   # attempt to use relevant run time e.g. tardis.toml


time $SEQ_PRISMS_BIN/align_prism.sh -f -a blastn  -r nt  -p "-evalue 1.0e-10  -dust \'20 64 1\' -max_target_seqs 1 -outfmt \'7 qseqid sseqid pident evalue staxids sscinames scomnames sskingdoms stitle\'"  -O $output_folder $sample_fasta 

base=`basename $sample_fasta`
qcid=`echo $base | awk -F- '{print $1}' -`

gunzip $output_folder/${qcid}*.results.gz
echo "All hits:"
grep "hits found" $output_folder/${qcid}*.results  | grep -v " 0 hits found" | wc

echo "Bacterial hits:"
grep -A 1 "hits found"  $output_folder/${qcid}*.results | egrep "^seq" | grep Bacteria | wc

echo "Non-bacterial hits:"
grep -A 1 "hits found"  $output_folder/${qcid}*.results | egrep "^seq" | grep -v Bacteria | wc

set +x

