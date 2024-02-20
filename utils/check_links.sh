#!/bin/bash
#
# check for links to the wrong fastq file in the link farm 
#
function get_wrong_flowcell() {
   # check for links to the wrong fastq file (wrong flowcell) , in the link farm
   # for all links in link farm
   for file in /dataset/hiseq/active/fastq-link-farm/*; do
      if [ -h $file ]; then
         bf=`basename $file`                           # get basename of link   e.g. SQ0395_CA5VDANXX_s_2_fastq.txt.gz
         fc=`echo $bf | awk -F_ '{print $2}' -`        # parse the flowcell from the link basename  e.g. CA5VDANXX 
         l=`readlink $file`                            # get link target e.g.  /dataset/hiseq_archive_1/archive/run_archives/170404_D00390_0292_ACA5VDANXX/processed/bcl2fastq/SQ0395/SQ0395_S2_L002_R1_001.fastq.gz
         echo $l | grep -q $fc > /dev/null 2>&1        # search for the flowcell parsed from the link name, in the link target
         if [ $? != 0 ]; then                          # report a bad link if not found
            echo $l " " $fc " " $bf                    # (report link target , flowcell and link name)
         fi 
      fi
   done
}

function get_wrong_sample() {
   # for all links in link farm
   for file in /dataset/hiseq/active/fastq-link-farm/*; do
      if [ -h $file ]; then
         bf=`basename $file`                           # get basename of link   e.g. SQ0395_CA5VDANXX_s_2_fastq.txt.gz
         sample=`echo $bf | awk -F_ '{print $1}' -`        # parse the sample from the link basename  e.g. SQ0395
         l=`readlink $file`                            # get link target e.g.  /dataset/hiseq_archive_1/archive/run_archives/170404_D00390_0292_ACA5VDANXX/processed/bcl2fastq/SQ0395/SQ0395_S2_L002_R1_001.fastq.gz
         echo $l | grep -q $sample > /dev/null 2>&1        # search for the sample parsed from the link name, in the link target
         if [ $? != 0 ]; then                          # report a bad link if not found

            # ignore if target is named "undetermined" 
            echo $l | grep -qi "undetermined" > /dev/null 2>&1 
            if [ $? != 0 ]; then 
               echo $l " " $sample " " $bf                    # (report link target , sample and link name)
            fi
         fi
      fi
   done
}


#get_wrong_flowcell
# results at 12/3/2021
#iramohio-01$ ./check_links.sh
#/dataset/MBIE_genomics4production/archive/Stoneflies/BJ1_H73TKAFXX_s_1_fastq.txt.gz   XTERNALXX   SQ100001_XTERNALXX_s_1_fastq.gz
#/dataset/MBIE_genomics4production/archive/Stoneflies/BJ2_H722LAFXX_s_1_fastq.txt.gz   XTERNALXX   SQ100002_XTERNALXX_s_2_fastq.gz
#/dataset/hiseq_archive_1/archive/run_archives/170321_D00390_0291_BCA63CANXX/processed/bcl2fastq/SQ0390_S7_L007_R1_001.fastq.gz   CAA99ANXX   test_CAA99ANXX_s_1_fastq.txt.gz
#
# these are OK - first two are non-standard links, the 3rd is a positive control !

get_wrong_sample
