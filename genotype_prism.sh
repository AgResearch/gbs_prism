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
   HAPMAP_FOLDER=hapMap
   OUT_FOLDER=KGD
   FORCE=no    # will clean the landmark target so it is rebuilt  


   help_text=$(cat << 'EOF'
usage :\n 
./genotype_prism.sh  [-h] [-n] [-d] [-x KGD_tassel] [-p genotyping parameters] [-m hapmap_folder] [-o outfolder] folder\n
example:\n
./genotype_prism.sh -x KGD_tassel3 /dataset/2023_illumina_sequencing_a/scratch/postprocessing/gbs/weevils_gbsx\n
./genotype_prism.sh -x KGD_tassel3 -p pooled /dataset/2023_illumina_sequencing_a/scratch/postprocessing/gbs/pooled_worms\n
EOF
)
   while getopts ":nhfC:x:p:m:o:" opt; do
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
       m)
         HAPMAP_FOLDER=$OPTARG     # relative name , e.g. hapMap
         ;;
       o)
         OUT_FOLDER=$OPTARG        # relative name , e.g. KGD
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
  echo HAPMAP_FOLDER=$HAPMAP_FOLDER
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
   cp ../run_GUSbase.R $OUT_DIR
   cp ../run_gusbase.sh $OUT_DIR ; chmod +x $OUT_DIR/run_gusbase.sh
   echo "
max_tasks=50
" > $OUT_DIR/tardis.toml
   echo "
export CONDA_ENVS_PATH=\"$GBS_PRISM_BIN/conda:/dataset/bioinformatics_dev/active/conda-env:$CONDA_ENVS_PATH\"
conda activate GUSbase 
" > $OUT_DIR/R_env.src
   echo "
export CONDA_ENVS_PATH=\"$GBS_PRISM_BIN/conda:/dataset/bioinformatics_dev/active/conda-env:$CONDA_ENVS_PATH\"
conda activate GUSbase
" > $OUT_DIR/gusbase_env.src

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

   if [ $FORCE == "yes" ]; then
      if [ -f $OUT_DIR/${genotype_moniker}.genotype_prism ]; then
         echo "force = yes, so removing landmark $OUT_DIR/${genotype_moniker}.genotype_prism so will be rebuilt"
         rm -f $OUT_DIR/${genotype_moniker}.genotype_prism
      fi
   fi

   if [ $ENGINE == "KGD_tassel3" ]; then

      echo "#!/bin/bash
export GBS_PRISM_BIN=$GBS_PRISM_BIN
export SEQ_PRISMS_BIN=$SEQ_PRISMS_BIN

cd $OUT_DIR  
if [ ! -d $OUT_FOLDER ]; then
   mkdir $OUT_FOLDER
fi
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/R_env.src  $OUT_DIR/run_kgd.sh $OUT_DIR/$OUT_FOLDER $GENO_PARAMETERS $HAPMAP_FOLDER \> $OUT_DIR/${genotype_moniker}.${OUT_FOLDER}.stdout  2\>$OUT_DIR/${genotype_moniker}.${OUT_FOLDER}.stderr 
if [ \$? != 0 ]; then
   echo \"genotype_prism.sh: error code returned from KGD process - quitting\"; exit 1
fi
# run gusbase
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/gusbase_env.src  $OUT_DIR/run_gusbase.sh $OUT_DIR/$OUT_FOLDER  \> $OUT_DIR/${genotype_moniker}.gusbase.${OUT_FOLDER}.stdout  2\>$OUT_DIR/${genotype_moniker}.gusbase.${OUT_FOLDER}.stderr
if [ \$? != 0 ]; then
   echo \"genotype_prism.sh: error code returned from KGD/gusbase process - quitting\"; exit 1
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
