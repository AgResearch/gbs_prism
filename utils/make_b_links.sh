#!/bin/sh
#
DRY_RUN=no
BPATH=none
help_text="

example : make_b_links.sh -b /dataset/hiseq/active/fastq-link-farm-b -q /dataset/2023_illumina_sequencing_a/scratch/postprocessing/illumina/novaseq/230607_A01439_0177_BHLTTWDMXY/SampleSheet/bclconvert \`find /dataset/hiseq/active/fastq-link-farm/ -name \"*HLTTWDMXY*\" -print\`
"

function get_opts() {

   while getopts ":nhb:q:" opt; do
   case $opt in
      n)
        DRY_RUN=yes
         ;;
      b)
        BPATH=$OPTARG
        ;;
      q)
        QPATH=$OPTARG
        ;;
      h)
        echo -e $help_text
        exit 0
        ;;
      \?)
        echo "Invalid option: -$OPTARG" >&2
        exit 1
        ;;
      :)
        echo "Option -$OPTARG requires an argument." >&2
        exit 1
        ;;
   esac
   done

   shift $((OPTIND-1))

   FILE_STRING=$@

   # this is needed because of the way we process args a "$@" - which
   # is needed in order to parse parameter sets to be passed to the
   # aligner (which are space-separated)
   declare -a files="(${FILE_STRING})";
   NUM_FILES=${#files[*]}
   for ((i=0;$i<$NUM_FILES;i=$i+1)) do
      files_array[$i]=${files[$i]}
   done
}

function process_targets() {
   for ((j=0;$j<$NUM_FILES;j=$j+1)) do
      file=${files_array[$j]}
      file_base=`basename $file`
      rp=`realpath $file`
      rp_base=`basename $rp`
      echo "processing $file_base"

      if [ ! -f $QPATH/$rp_base ]; then
         echo "could not find $QPATH/$rp_base to link to "
      else
         echo "will execute ln -s $QPATH/$rp_base $BPATH/$file_base"
      fi

      if [ $DRY_RUN != "no" ]; then
         echo "(dry run !)"
      else
         ln -s $QPATH/$rp_base $BPATH/$file_base
      fi 

     
   done
}


function main() {
   get_opts "$@"
   process_targets
}


main "$@"




