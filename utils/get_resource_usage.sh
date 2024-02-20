#!/bin/bash

function get_fastq_total() {
   for mylink in /dataset/hiseq/active/fastq-link-farm/*.txt.gz; do
      myrp=`realpath $mylink`
      mysize=`du -b $myrp`
      echo -e "${mylink}\t${myrp}\t${mysize}\n"
   done
}

function get_overall_cpu() {
   #for sdate in 2023-08-01 2023-08-03 ; do
   #for sdate in 2023-08-29 2023-08-30 ; do
   for sdate in 2023-08-27 2023-08-28 ; do
      sacct -S${sdate} -a -ojobid,start,end,alloccpu,cputime | column -t > ${sdate}.sacct.txt
   done
}


#get_fastq_total
get_overall_cpu
