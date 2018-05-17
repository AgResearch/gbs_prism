#!/bin/bash
#
# this prism supports a basic q/c gbs analysis  of a set of either tag count or sequence files 
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


   help_text=$(cat << 'EOF'
usage : 
./gbs_prism.sh  [-h] [-n] [-d] [-x gbsx|tassel3] [-l sample_info ]  [-e enzymeinfo] -O outdir input_file_name(s)
example:
./gbs_prism.sh -n -x gbsx -l  /dataset/hiseq/active/bin/gtseq_prism/source/LocusInfo_Casein_DGAT_new2.csv -O /dataset/miseq/scratch/postprocessing/gtseq/180403_M02412_0073_000000000-D3JC9/gbss /dataset/miseq/active/180403_M02412_0073_000000000-D3JC9/Data/Intensities/BaseCalls/BBG491876_S55_L001_R1_001.fastq

Notes:

* only use this script to process more than one fastq file, where all files relate to the sample info file 
  (e.g. keyfile) you supply (i.e. all files relate to the same library)

* for GBSX, enzyme_info is an optional filename, of a file containing cut-sites for non-default enzymes). For
  tassel3 it is mandatory and is the name of the enzyme to use

EOF
)

   help_text="
\n
.
"
   while getopts ":nhO:C:D:x:l:e:" opt; do
   case $opt in
       n)
         DRY_RUN=yes
         ;;
       d)
         DEBUG=yes
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
       x)
         ENGINE=$OPTARG         
         ;;
       e)
         ENZYME_INFO=$OPTARG
         ;;
       l)
         SAMPLE_INFO=$OPTARG    
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


function check_opts() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "please set SEQ_PRISMS_BIN environment variable"
      exit 1
   fi

   if [ ! -d $OUT_DIR ]; then
      echo "OUT_DIR $OUT_DIR not found"
      exit 1
   fi

   if [[ $HPC_TYPE != "local" && $HPC_TYPE != "slurm" ]]; then
      echo "HPC_TYPE must be one of local, slurm"
      exit 1
   fi


   if [ ! -f $SAMPLE_INFO ]; then
      echo "could not find $SAMPLE_INFO"
      exit 1
   fi

   if [[ ( $ENGINE != "gbsx" ) && ( $ENGINE != "tassel3" ) ]] ; then
      echo "gbser engines supported : tassel3, gbsx (not $ENGINE ) "
      exit 1
   fi

   if [ ! -z $ENZYME_INFO ]; then
      if [ $ENGINE == "gbsx" ]; then
         if [ ! -f $ENZYME_INFO ]; then 
            echo "could not find $ENZYME_INFO"
            exit 1
         fi
      fi
   elif [ $ENGINE == "tassel3" ]; then
      echo "must specify enzyme , for tassel3 (should match enzyme specified in keyfile)"
      exit 1
   fi

}

function echo_opts() {
  echo OUT_DIR=$OUT_DIR
  echo DRY_RUN=$DRY_RUN
  echo DEBUG=$DEBUG
  echo HPC_TYPE=$HPC_TYPE
  echo FILES=${files_array[*]}
  echo ENGINE=$ENGINE
  echo SAMPLE_INFO=$SAMPLE_INFO
  echo ENZYME_INFO=$ENZYME_INFO
}


#
# edit this method to set required environment (or set up
# before running this script)
#
function configure_env() {
   cd $SEQ_PRISMS_BIN
   cp ../gbs_prism.sh $OUT_DIR
   cp ../seq_prisms/data_prism.py $OUT_DIR
   cp ../gbs_prism.mk $OUT_DIR
   cp $SAMPLE_INFO $OUT_DIR
   cp $ENZYME_INFO $OUT_DIR
   echo "
max_tasks=50
" > $OUT_DIR/tardis.toml
   echo "
source activate tassel3
" > $OUT_DIR/tassel3_env.src
   cd $OUT_DIR
}


function check_env() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "SEQ_PRISMS_BIN not set - exiting"
      exit 1
   fi
}

function get_targets() {
   # make a target moniker for each input file and write associated 
   # ENGINE wrapper, which will be called by make 

   rm -f $OUT_DIR/gbs_targets.txt

  
   for ((j=0;$j<$NUM_FILES;j=$j+1)) do
      file=${files_array[$j]}
      file_base=`basename $file`
      parameters_moniker=`basename $SAMPLE_INFO`
      if [ ! -z $ENZYME_INFO ]; then
         parameters_moniker="${parameters_moniker}.$ENZYME_INFO"
      fi
      

      if [ $ENGINE == "gbsx" ]; then    
         gbs_moniker=${file_base}.${parameters_moniker}.${ENGINE}
         echo $OUT_DIR/${gbs_moniker}.gbs_prism >> $OUT_DIR/gbs_targets.txt
         script=$OUT_DIR/${gbs_moniker}.sh
      elif [ $ENGINE == "tassel3" ]; then    
         gbs_moniker=${parameters_moniker}.${ENGINE}
         echo $OUT_DIR/${gbs_moniker}.gbs_prism > $OUT_DIR/gbs_targets.txt   # one line only 
         script=$OUT_DIR/${gbs_moniker}.sh
      fi

      if [ -f script ]; then
         if [ ! $FORCE == yes ]; then
            echo "found existing gbs script $script  - will re-use (use -f to force rebuild of scripts) "
            continue
         fi
      fi

      base=`basename $file`

      if [ $ENGINE == "tassel3" ]; then
         # we only generate a single target , even if there are multiple files. The setup
         # of the target involves configuring output sub-folders
         # structure , so set this up 
         mkdir -p ${OUT_DIR}/key
         mkdir -p ${OUT_DIR}/Illumina
         mkdir -p ${OUT_DIR}/tagCounts
         cp -s $file ${OUT_DIR}/Illumina
         sample_info_base=`basename $SAMPLE_INFO`
         cp -fs  $OUT_DIR/$sample_info_base ${OUT_DIR}/key

         echo "#!/bin/bash
cd $OUT_DIR  
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src run_pipeline.pl -Xms512m -Xmx5g -fork1 -UFastqToTagCountPlugin -w ./ -c 1 -e $ENZYME_INFO  -s 400000000 -endPlugin -runfork1 \> $OUT_DIR/${gbs_moniker}.stdout 2\> $OUT_DIR/${gbs_moniker}.stderr
        " > $script 
         chmod +x $script
      elif [ $ENGINE == "gbsx" ]; then 
         sample_info_base=`basename $SAMPLE_INFO`
         if [ -f "$ENZYME_INFO" ]; then
            ENZYME_PHRASE="-ea $ENZYME_INFO"
         fi
         cat << THERE > $script
#!/bin/bash
#
# note , currently using -k option for debugging - remove this 
#
set -x
base=`basename $file`
mkdir ${OUT_DIR}/${base}.gbsed
cd ${OUT_DIR}
# this will gbs in parallel into numbered subfolders of the tardis working folder
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR java -jar $SEQ_PRISMS_BIN/../bin/GBSX_v1.3.jar --gbser $ENZYME_PHRASE -f1 _condition_fastq_input_$file -i $OUT_DIR/$sample_info_base  -o _condition_output_$OUT_DIR/${base}.gbsed -lf TRUE -gzip FALSE \> _condition_uncompressedtext_output_$OUT_DIR/${gbs_moniker}.stdout 2\> _condition_uncompressedtext_output_$OUT_DIR/${gbs_moniker}.stderr
# for each distinct sample , combine all the slices 
# get the distinct samples
for outfile in tardis_*/\${base}.*.gbsed/*.fastq; do
   sample=\`basename \$outfile\`
   echo \$sample >> $OUT_DIR/\${base}.gbsed/sample_list
done

# combine all slices 
for sample in \`cat $OUT_DIR/\${base}.gbsed/sample_list\`; do
   cat tardis_*/\${base}.*.gbsed/\${sample}  > $OUT_DIR/\${base}.gbsed/\${sample}
done
THERE
         chmod +x $script
      fi
   done 

}

function fake_prism() {
   echo "dry run ! 

   "
   exit 0
}

function run_prism() {
   # do genotyping
   make -f gbs_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_DIR/gbs_targets.txt` > $OUT_DIR/gbs_prism.log 2>&1

   # run summaries
}

function html_prism() {
   echo "tba" > $OUT_DIR/gbs_prism.html 2>&1
}

function clean() {
   echo "skipping clean for now"
   #rm -rf $OUT_DIR/tardis_*
   #rm $OUT_DIR/*.fastq
}


function main() {
   get_opts "$@"
   check_opts
   echo_opts
   check_env
   configure_env
   get_targets
   if [ $DRY_RUN != "no" ]; then
      fake_prism
   else
      run_prism
      if [ $? == 0 ] ; then
         html_prism
         clean
      else
         echo "error state from sample run - skipping html page generation and clean-up"
         exit 1
      fi
   fi
}


set -x
main "$@"
set +x
