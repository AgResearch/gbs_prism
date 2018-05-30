#!/bin/sh

export SEQ_PRISMS_BIN=/dataset/hiseq/active/bin/gbs_prism/seq_prisms 

function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_DIR=""
   FORCE=no
   PRISM_ARGS=""
   PRISM_NAME=all


   help_text="
\n
./run_prisms.sh  [-h] [-n] [-d] [-f] [-P prism_name] [-x script] [-r prism_args] -O outdir [-C local|slurm ] input_file_names\n
\n
\n
example:\n
run_prisms.sh -n -P demultiplex -r /dataset/OARv3.0/active/current_version/sheep.v3.0.14th.final.fa -O /dataset/miseq/scratch/postprocessing/gtseq/180403_M02412_0073_000000000-D3JC9/alignments  /dataset/miseq/active/180403_M02412_0073_000000000-D3JC9/Data/Intensities/BaseCalls/BBG491869_S28_L001_R1_001.fastq\n
\n
"

   # defaults:
   while getopts ":nhfO:C:s:m:a:r:P:x:" opt; do
   case $opt in
       n)
         DRY_RUN=yes
         ;;
       d)
         DEBUG=yes
         ;;
       f)
         FORCE=yes
         ;;
       h)
         echo -e $help_text
         exit 0
         ;;
       O)
         OUT_DIR=$OPTARG
         ;;
       C)
         HPC_TYPE=$OPTARG
         ;;
       P)
         PRISM_NAME=$OPTARG
         ;;
       r)
         PRISM_ARGS=$OPTARG
         ;;
       x)
         PRISM_OPT_SCRIPT=$OPTARG
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

   FILES=$@
}

function check_opts() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "please set SEQ_PRISMS_BIN environment variable"
      exit 1
   fi

   if [[ ( $PRISM_NAME != "kmers" ) && ( $PRISM_NAME != "genotype" )  ]]; then
      echo "unknown analysis : $PRISM_NAME"
      exit 1
   fi

   if [ $PRISM_NAME == "genotype"  ]; then
      # argument should be a file of locus info 
      if [ ! -f $PRISM_ARGS ]; then
         echo "$PRISM_ARGS should be a file of locus info"
      fi
   elif [ $PRISM_NAME == "bwa" ]; then
      ls -l ${PRISM_ARGS}* > /dev/null 2>&1
      if [ $? != 0 ]; then
         echo "$PRISM_ARGS should be a bwa reference"
      fi
   fi
}

function echo_opts() {
   echo ""
}


function check_env() {
   echo ""
}

function configure_env() {
   echo ""
}


function get_prisms() {
   git clone git@github.com:AgResearch/seq_prisms.git
}

function fake_prism() {
    if [ $PRISM_NAME == "bwa" ]; then 
       seq_prisms/align_prism.sh -n -m 3 -f -a bwa -r $PRISM_ARGS -O $OUT_DIR  $FILES 
    elif [ $PRISM_NAME == "genotype" ]; then
       ./genotype_prism.sh -n -g $PRISM_OPT_SCRIPT -l $PRISM_ARGS -O $OUT_DIR $FILES 
    else 
       echo "unsupported prism : $PRISM_NAME"
       exit 1
    fi
}

function run_prism() {
    if [ $PRISM_NAME == "kmers" ]; then
       seq_prisms/kmer_prism.sh -p "-k 6" -a fastq -O $OUT_DIR $FILES
    elif [ $PRISM_NAME == "gbs" ]; then
       ./gbs_prism.sh -g $PRISM_OPT_SCRIPT -l $PRISM_ARGS -O $OUT_DIR $FILES
    else
       echo "unsupported prism : $PRISM_NAME"
       exit 1
    fi
}



function html_prism() {
   echo "tba" > $OUT_DIR/align_prism.html 2>&1
}


function main() {
   get_opts $@
   check_opts
   echo_opts
   check_env
   configure_env
   if [ $DRY_RUN != "no" ]; then
      fake_prism
   else
      run_prism
      if [ $? == 0 ] ; then
         html_prism
      else
         echo "error state from prism run - skipping html page generation"
         exit 1
      fi
   fi
}


main "$@"
