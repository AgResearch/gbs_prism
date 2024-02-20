#!/bin/bash


GBS_PRISM_BIN=/dataset/gseq_processing/active/bin/gbs_prism
PROCESSING_ROOT=/dataset/gseq_processing/scratch/gbs
TEMP=/dataset/gseq_processing/scratch/temp
INCREMENTAL=0
INTERACTIVE=no
RESET_BASE=0

function read_answer_with_default() {
   if [ $INTERACTIVE == yes ]; then
      read answer
      if [ -z "$answer" ]; then
         answer=$@
      fi
   else
      answer=$@
   fi
}


function get_opts() {


   help_text=$(cat << 'EOF'
usage :\n
./SelfRelDepth.sh [-h] [-I] [-R] run_name run_name . . . ]\n
EOF
)
   while getopts ":hIRi" opt; do
   case $opt in
       h)
         echo -e $help_text
         exit 0
         ;;
       I)
         INCREMENTAL=1
         ;;
       i)
         INTERACTIVE=yes
         ;;
       R)
         RESET_BASE=1
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

   RUNS=$@

}

function get_files_to_process() {
   # for each base , find the available data files and process them
   echo "searching for GHW05.RData files to process..."
   echo "press enter to continue or CTRL-C to exit"
   read_answer_with_default y
   rm  $TEMP/SelfRelDepth.files_to_process.tmp
   rm  $TEMP/SelfRelDepth.files_to_process.diff
   set -x

   if [ $RESET_BASE == 1 ]; then
      cp 
   fi 
   if [ -z "$RUNS" ]; then 
      for base_dir in $PROCESSING_ROOT/*; do
         if [ -d $base_dir ]; then
            find $base_dir -maxdepth 3  -name "GHW05.RData" -print | grep 'KGD/GHW05.RData' - >> $TEMP/SelfRelDepth.files_to_process.tmp
         fi
      done
   else
      for run in $RUNS; do
         base_dir=$PROCESSING_ROOT/$run
         if [ -d $base_dir ]; then
            find $base_dir -maxdepth 2  -name "GHW05.RData" -print | grep 'KGD/GHW05.RData' - >> $TEMP/SelfRelDepth.files_to_process.tmp 
         fi
      done
   fi
   cat $GBS_PRISM_BIN/SelfRelDepth.files_to_process.other $TEMP/SelfRelDepth.files_to_process.tmp | sort -u > $TEMP/SelfRelDepth.files_to_process.update 

   if [ $INCREMENTAL == 1 ]; then
      diff $TEMP/SelfRelDepth.files_to_process $TEMP/SelfRelDepth.files_to_process.update | grep ">" | awk '{print $2}' - > $TEMP/SelfRelDepth.files_to_process.diff
   else
      cp -s $TEMP/SelfRelDepth.files_to_process.update $TEMP/SelfRelDepth.files_to_process.diff
   fi
   chmod o+w $TEMP/SelfRelDepth.files_to_process.diff  > /dev/null 2>&1
   chmod o+w $TEMP/SelfRelDepth.files_to_process.update  > /dev/null 2>&1
   chmod o+w $TEMP/SelfRelDepth.files_to_process.tmp  > /dev/null 2>&1

   set +x
}

function process_files() {
   num_to_process=`wc $TEMP/SelfRelDepth.files_to_process.diff | awk '{print $1}' -`
   echo "will process file list $TEMP/SelfRelDepth.files_to_process.diff ( $num_to_process files )" 
   echo "(will overwrite $TEMP/SelfRelDepth.out.diff)"
   echo "press any key to continue (or CTRL-C to exit)"
   read_answer_with_default y
   echo "processing..."
   rm $TEMP/SelfRelDepth.out.diff
   set -x
   for file in `cat $TEMP/SelfRelDepth.files_to_process.diff`; do
      KGDdir=`dirname $file`
      Rscript --vanilla  $GBS_PRISM_BIN/SelfRelDepth.r KGDdir=$KGDdir  >> $TEMP/SelfRelDepth.out.diff 2>$TEMP/SelfRelDepth.r.stderr
   done
   set +x
   chmod o+w $TEMP/SelfRelDepth.out.diff  > /dev/null 2>&1
   chmod o+w $TEMP/SelfRelDepth.r.stderr  > /dev/null 2>&1
   
}

function annotate_output() {
   echo "annotating output file $TEMP/SelfRelDepth.out.diff , to $TEMP/SelfRelDepth.out.annotated.diff ..."
   cat $TEMP/SelfRelDepth.out.diff | $GBS_PRISM_BIN/annotateSelfRelDepth.py 1>$TEMP/SelfRelDepth.out.annotated.diff 2>$TEMP/SelfRelDepth.out.annotated.diff.stderr
   chmod o+w $TEMP/SelfRelDepth.out.annotated.diff  > /dev/null 2>&1
   chmod o+w $TEMP/SelfRelDepth.out.annotated.diff.stderr  > /dev/null 2>&1
}

function make_html_page() {
   echo "creating html page /dataset/gseq_processing/scratch/gbs/SelfRelDepth_details.html ..."
   cat $TEMP/SelfRelDepth.out.annotated $TEMP/SelfRelDepth.out.annotated.diff | $GBS_PRISM_BIN/SelfRelDepthtoHTML.py > /dataset/gseq_processing/scratch/gbs/SelfRelDepth_details.html
   chmod o+w /dataset/gseq_processing/scratch/gbs/SelfRelDepth_details.html > /dev/null 2>&1
}



get_opts "$@"  

if [ $RESET_BASE == 1 ]; then
   set -x
   cp $TEMP/SelfRelDepth.files_to_process $TEMP/SelfRelDepth.files_to_process.old
   cp $TEMP/SelfRelDepth.files_to_process.update $TEMP/SelfRelDepth.files_to_process
   chmod o+w $TEMP/SelfRelDepth.files_to_process.update $TEMP/SelfRelDepth.files_to_process
   set +x
   exit
fi


get_files_to_process
process_files
annotate_output
make_html_page
