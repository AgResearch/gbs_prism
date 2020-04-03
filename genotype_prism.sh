#!/bin/bash
#
# this prism supports a basic q/c genotyping (by sequencing) analysis.It assumes that the demultiplex prism has been run.
# (there is some overlap between the demultiplex and gsb analysis )
# 
#

declare -a files_array

function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_DIR=""
   ENZYME_INFO=""
   GENO_PARAMETERS=""
   FORCE=no


   help_text=$(cat << 'EOF'
usage :\n 
./genotype_prism.sh  [-h] [-n] [-d] [-x KGD_tassel] [-p genotyping parameters] -O outdir folder\n
example:\n
./genotype_prism.sh -x KGD_tassel3 /dataset/hiseq/scratch/postprocessing/gbs/weevils_gbsx\n
./genotype_prism.sh -x KGD_tassel3 -p pooled /dataset/hiseq/scratch/postprocessing/gbs/pooled_worms\n
EOF
)
   while getopts ":nhfO:C:O:x:p:" opt; do
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
       C)
         HPC_TYPE=$OPTARG
         ;;
       x)
         ENGINE=$OPTARG         
         ;;
       p)
         GENO_PARAMETERS=$OPTARG
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

   DEMULTIPLEX_FOLDER=$1
   OUT_DIR=$DEMULTIPLEX_FOLDER

}


function check_opts() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "please set SEQ_PRISMS_BIN environment variable"
      exit 1
   fi

   if [ ! -d $OUT_DIR ]; then
      echo "out_dir $OUT_DIR not found"
      exit 1
   fi

   if [ ! -d $DEMULTIPLEX_FOLDER ]; then
      echo "demultiplex folder $DEMULTIPLEX_FOLDER not found"
      exit 1
   fi

   if [[ $HPC_TYPE != "local" && $HPC_TYPE != "slurm" ]]; then
      echo "HPC_TYPE must be one of local, slurm"
      exit 1
   fi

   if [[ ( $ENGINE != "KGD_tassel3" ) ]] ; then
      echo "genotyping engines supported : KGD_tassel3 (not $ENGINE ) "
      exit 1
   fi

}

function echo_opts() {
  echo OUT_DIR=$OUT_DIR
  echo DEMULTIPLEX_FOLDER=$DEMULTIPLEX_FOLDER
  echo DRY_RUN=$DRY_RUN
  echo DEBUG=$DEBUG
  echo HPC_TYPE=$HPC_TYPE
  echo FILES=${files_array[*]}
  echo ENGINE=$ENGINE
  echo GENO_PARAMETERS=$GENO_PARAMETERS
}


#
# edit this method to set required environment (or set up
# before running this script)
#
function configure_env() {
   cd $SEQ_PRISMS_BIN
   cp ../genotype_prism.sh $OUT_DIR
   cp ../seq_prisms/data_prism.py $OUT_DIR
   cp ../genotype_prism.mk $OUT_DIR
   cp ../run_kgd.sh $OUT_DIR ; chmod +x $OUT_DIR/run_kgd.sh
   cp ../run_kgd.R $OUT_DIR
   echo "
max_tasks=50
" > $OUT_DIR/tardis.toml
   echo "
export CONDA_ENVS_PATH=\"$GBS_PRISM_BIN/conda:/dataset/bioinformatics_dev/active/conda-env:$CONDA_ENVS_PATH\"
conda activate gbs_prism
" > $OUT_DIR/R_env.src

   cd $OUT_DIR

   # KGD lives here 
   cd $SEQ_PRISMS_BIN/..
   if [ ! -d KGD ]; then 
      git clone git@github.com:AgResearch/KGD.git
   fi 
   cd KGD 
}


function check_env() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "SEQ_PRISMS_BIN not set - exiting"
      exit 1
   fi
}

function get_targets() {
   # make a target moniker  and write associated 
   # ENGINE wrapper, which will be called by make 

   rm -f $OUT_DIR/genotype_targets.txt

   file_base=`basename $DEMULTIPLEX_FOLDER`
   genotype_moniker=${file_base}.${ENGINE}
   echo $OUT_DIR/${genotype_moniker}.genotype_prism >> $OUT_DIR/genotype_targets.txt
   script=$OUT_DIR/${genotype_moniker}.genotype_prism.sh
   if [ -f $script ]; then
      if [ ! $FORCE == yes ]; then
         echo "found existing genotype script $script  - will re-use (use -f to force rebuild of scripts) "
         continue
      fi
   fi

   if [ $ENGINE == "KGD_tassel3" ]; then

      echo "#!/bin/bash
cd $OUT_DIR  
if [ ! -d KGD ]; then
   mkdir KGD
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/R_env.src  $OUT_DIR/run_kgd.sh $OUT_DIR/KGD $GENO_PARAMETERS \> $OUT_DIR/${genotype_moniker}.KGD.stdout  2\>$OUT_DIR/${genotype_moniker}.KGD.stderr 
fi
if [ \$? != 0 ]; then
   echo \"genotype_prism.sh: error code returned from KGD process - quitting\"; exit 1
fi
     " > $script 
      chmod +x $script
   fi
}

function fake() {
   echo "dry run ! 

   "
   exit 0
}

function run() {
   # do genotyping
   cd $OUT_DIR
   make -f genotype_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_DIR/genotype_targets.txt` > $OUT_DIR/genotype_prism.log 2>&1

   # run summaries
}

function html() {
   echo "tba" > $OUT_DIR/genotype_prism.html 2>&1
}

function clean() {
   nohup rm -rf $OUT_DIR/tardis_* > $OUT_DIR/genotype_clean.log 2>&1 &
}


function main() {
   get_opts "$@"
   check_opts
   echo_opts
   check_env
   configure_env
   get_targets
   if [ $DRY_RUN != "no" ]; then
      fake
   else
      run
      if [ $? == 0 ] ; then
         html
         clean
      else
         echo "error state from genotype run - skipping html page generation and clean-up"
         exit 1
      fi
   fi
}


set -x
main "$@"
set +x
