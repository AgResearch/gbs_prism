#!/bin/sh

# creates links to the fastq files in the GBS processing folder
# The argument is the folder in which to link - e.g.
#### /dataset/hiseq/scratch/postprocessing/150925_D00390_0235_BC6K0YANXX.gbs_in_progress/SQ0123.sample_in_progress/uneak_in_progress/Illumina
#    /dataset/hiseq/scratch/postprocessing/170413_D00390_0295_BCA5EWANXX.gbs_in_progress/SQ0419.sample_in_progress/uneak_in_progress/PstI.enzyme/Illumina
#    /dataset/hiseq/scratch/postprocessing/170413_D00390_0295_BCA5EWANXX.gbs_in_progress/SQ0419.sample_in_progress/uneak_in_progress/Deer.PstI.cohort/Illumina


# get the flowcellid so that we can only include fastq files related to this flowcell 
# (some libraries are run cumulatively across many keyfiles)

fcid=`echo $1 | awk -F/ '{print $6}' -`
fcid=`echo $fcid | awk -F. '{print $1}' -`
fcid=`echo $fcid | awk -F_ '{print substr($4,2)}' -`

echo "linking fastq files in $1"
set -x
fastq_link=`psql -U agrbrdf -d agrbrdf -h invincible -v gbs_fastq_link_folder="'$1'" -f $GBS_BIN/database/get_fastq_link.psql -q | egrep -i $fcid | sed 's/ //g' -`

for link in $fastq_link; do
   if [ ! -h $link ]; then
      echo "link_fastq_files.sh : ERROR link $link does not exist"
      exit 1
   fi

   link_base=`basename $link`
   cp -s $link $1/$link_base
done
set +x

exit 0
