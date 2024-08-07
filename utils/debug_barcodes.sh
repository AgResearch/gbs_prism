#!/bin/bash
#
# try to match common sequences in the GBS barcode position in a fastq file, with barcodes in the database.
#
if [ -z "$1" ]; then
   echo "examples : 
debug_barcodes.sh /bifo/scratch/2024_illumina_sequencing_e/postprocessing/gbs/230623_A01439_0188_AHFFGNDRX3/SQ2128.all.microbes.PstI/./Illumina/SQ2128_HFFGNDRX3_s_1_fastq.txt.gz
"
   exit 1
elif [ ! -f $1 ]; then
   echo "$1 does not exist - should be path to a compressed fastq file containing GBS data"
   exit 1
fi


function get_summary() {
   for file in $1; do
      echo "looking for known barcodes in $file"
      for code in `gunzip -c $file | egrep -A 1 --no-group-separator "^@" | egrep -v "^@" | awk '{print substr($1,1,10);}' - | head -1000000 | sort | uniq -c | sort -rn -k1,1  | head -400 | awk '{print $2}' -`; do grep $code /dataset/gseq_processing/active/bin/gquery/database/t_BarcodePlates.csv; done | sort | uniq -c | sort -n -k1,1 | awk '{print $2}' - | awk -F, '{print $1}' - | sort | uniq -c
      echo "
      "
   done
}

get_summary $1
