#!/bin/bash
#
# this prism supports demultiplex of a set of sequence files , all of which contain
# multiplexed GBS sequencing data as specified by a sample information file.
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
   FORCE=no
   SPLIT=no
   

   help_text=$(cat << 'EOF'
usage : 
./demultiplex_prism.sh  [-h] [-n] [-d] [-x gbsx|tassel3_qc|tassel3] [-l sample_info ]  [-e enzymeinfo] -O outdir input_file_name(s)
example:

Notes:

* only use this script to process more than one fastq file, where all files relate to the sample info file 
  (e.g. keyfile) you supply (i.e. all files relate to the same library)

* for GBSX, enzyme_info is an optional filename, of a file containing cut-sites for non-default enzymes). For
  tassel3 it is mandatory and is the name of the enzyme to use

EOF
)
   while getopts ":nhSfO:C:x:l:e:" opt; do
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
       x)
         ENGINE=$OPTARG         
         ;;
       e)
         ENZYME_INFO=$OPTARG
         ;;
       l)
         SAMPLE_INFO=$OPTARG    
         ;;
       S)
         SPLIT=yes
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

   if [[ ( $ENGINE != "gbsx" ) && ( $ENGINE != "tassel3_qc" ) && ( $ENGINE != "tassel3" ) ]] ; then
      echo "demultiplexer engines supported : tassel3, gbsx , tassel3_qc (not $ENGINE ) "
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
   # copy scripts we need to outfolder
   cd $GBS_PRISM_BIN
   cp demultiplex_prism.sh $OUT_DIR
   cp demultiplex_prism.mk $OUT_DIR
   cp $SAMPLE_INFO $OUT_DIR
   cp $ENZYME_INFO $OUT_DIR
   cp $GBS_PRISM_BIN/etc/larger_mem_slurm_array_job $OUT_DIR

  
   # set up the environment includes that we will need - these activate 
   # environments 

   echo "
max_tasks=50
jobtemplatefile = \"$OUT_DIR/larger_mem_slurm_array_job\"
" > $OUT_DIR/tardis_demultiplex.toml
   if [ -f  $OUT_DIR/tardis.toml ]; then 
      cp $OUT_DIR/tardis.toml $OUT_DIR/tardis.toml.orig
   fi
   cp  $OUT_DIR/tardis_demultiplex.toml $OUT_DIR/tardis.toml
   cp $GBS_BIN/etc/larger_mem_slurm_array_job $OUT_DIR
   echo "
conda activate tassel3
" > $OUT_DIR/tassel3_env.src
   cd $OUT_DIR
}

function check_env() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "SEQ_PRISMS_BIN not set - exiting"
      exit 1
   fi
   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "GBS_PRISM_BIN not set - exiting"
      exit 1
   fi

}

function get_targets() {
   # make a target moniker for each input file and write associated 
   # ENGINE wrapper, which will be called by make 

   rm -f $OUT_DIR/demultiplex_targets.txt

   for ((j=0;$j<$NUM_FILES;j=$j+1)) do
      file=${files_array[$j]}
      file_base=`basename $file`
      parameters_moniker=`basename $SAMPLE_INFO`
      if [ ! -z $ENZYME_INFO ]; then
         parameters_moniker="${parameters_moniker}.$ENZYME_INFO"
      fi
      

      if [ $ENGINE == "gbsx" ]; then    
         demultiplex_moniker=${file_base}.${parameters_moniker}.${ENGINE}
         echo $OUT_DIR/${demultiplex_moniker}.demultiplex_prism >> $OUT_DIR/demultiplex_targets.txt
         script=$OUT_DIR/${demultiplex_moniker}.demultiplex_prism.sh
      elif [[ ( $ENGINE == "tassel3" ) || ( $ENGINE == "tassel3_qc" ) ]]; then    
         demultiplex_moniker=${parameters_moniker}.${ENGINE}
         echo $OUT_DIR/${demultiplex_moniker}.demultiplex_prism > $OUT_DIR/demultiplex_targets.txt   # one line only 
         script=$OUT_DIR/${demultiplex_moniker}.demultiplex_prism.sh
      fi

      if [ -f script ]; then
         if [ ! $FORCE == yes ]; then
            echo "found existing demultiplex script $script  - will re-use (use -f to force rebuild of scripts) "
            continue
         fi
      fi

      base=`basename $file`

      if [ $ENGINE == "tassel3" ]; then
         # we only generate a single target , even if there are multiple files. The setup
         # of the target involves configuring output sub-folders
         # structure , so set this up 
         if [ ! -d ${OUT_DIR}/key ] ; then 
            mkdir -p ${OUT_DIR}/key
            sample_info_base=`basename $SAMPLE_INFO`
            cp -fs  $OUT_DIR/$sample_info_base ${OUT_DIR}/key
         fi
         if [ ! -d ${OUT_DIR}/Illumina ]; then
            mkdir -p ${OUT_DIR}/Illumina
         fi
         cp -s $file ${OUT_DIR}/Illumina

         echo "#!/bin/bash
cd $OUT_DIR  
if [ ! -d tagCounts ]; then 
   mkdir tagCounts 
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src run_pipeline.pl -Xms512m -Xmx5g -fork1 -UFastqToTagCountPlugin -w ./ -c 1 -e $ENZYME_INFO  -s 400000000 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stdout 2\>$OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from FastqToTagCount process - quitting\"; exit 1
fi
        " > $script 
         chmod +x $script
      elif [ $ENGINE == "tassel3_qc" ]; then
         # as above - but this one also runs downstream processsing as a convenience 
         if [ ! -d ${OUT_DIR}/key ] ; then 
            mkdir -p ${OUT_DIR}/key
            sample_info_base=`basename $SAMPLE_INFO`
            cp -fs  $OUT_DIR/$sample_info_base ${OUT_DIR}/key
         fi
         if [ ! -d ${OUT_DIR}/Illumina ]; then
            mkdir -p ${OUT_DIR}/Illumina
         fi
         cp -s $file ${OUT_DIR}/Illumina

         echo "#!/bin/bash
cd $OUT_DIR  
if [ ! -d tagCounts ]; then 
   mkdir tagCounts 
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src run_pipeline.pl -Xms512m -Xmx5g -fork1 -UFastqToTagCountPlugin -w ./ -c 1 -e $ENZYME_INFO  -s 400000000 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stdout 2\>$OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from FastqToTagCount process - quitting\"; exit 1
fi

if [ ! -d mergedTagCounts ]; then 
   mkdir mergedTagCounts
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UMergeTaxaTagCountPlugin -w ./ -m 600000000 -x 100000000 -c 5 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.MergeTaxaTagCount.stdout  2\>$OUT_DIR/${demultiplex_moniker}.MergeTaxaTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from MergeTaxaTagCount process - quitting\"; exit 2
fi

if [ ! -d tagPair ]; then 
   mkdir tagPair
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTagCountToTagPairPlugin -w ./ -e 0.03 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.TagCountToTagPair.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TagCountToTagPair.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TagCountToTagPair process - quitting\"; exit 3
fi

if [ ! -d tagsByTaxa ]; then 
   mkdir tagsByTaxa
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTagPairToTBTPlugin -w ./ -endPlugin -runfork1  \> $OUT_DIR/${demultiplex_moniker}.TagPairToTBT.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TagPairToTBT.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TagPairToTBT process - quitting\"; exit 4
fi

if [ ! -d mapInfo ] ; then 
   mkdir mapInfo
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTBTToMapInfoPlugin -w ./ -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.TBTToMapInfo.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TBTToMapInfo.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TBTToMapInfo process - quitting\"; exit 5
fi

if [ ! -d hapMap ]; then
   mkdir hapMap
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UMapInfoToHapMapPlugin -w ./ -mnMAF 0.03 -mxMAF 0.5 -mnC 0.1 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.MapInfoToHapMap.stdout  2\>$OUT_DIR/${demultiplex_moniker}.MapInfoToHapMap.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from MapInfoToHapMap process - quitting\"; exit 6
fi
        " > $script 
         chmod +x $script
      elif [ $ENGINE == "gbsx" ]; then 
         sample_info_base=`basename $SAMPLE_INFO`
         if [ -f "$ENZYME_INFO" ]; then
            ENZYME_PHRASE="-ea $ENZYME_INFO"
         fi
         if [ $SPLIT == "yes" ]; then 
            # can optionally split the input fastq and launch demultiplex of the splits in parallel - however this 
            # usually is slower than just launching a single job
            cat << END_SPLIT > $script
#!/bin/bash
#
# note , currently using -k option for debugging - remove this 
#
set -x
base=`basename $file`
mkdir ${OUT_DIR}/${base}.demultiplexed
cd ${OUT_DIR}
# this will demultiplex in parallel into numbered subfolders of the tardis working folder
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR java -jar $SEQ_PRISMS_BIN/../bin/GBSX_v1.3.jar --Demultiplexer $ENZYME_PHRASE -f1 _condition_fastq_input_$file -i $OUT_DIR/$sample_info_base  -o _condition_output_$OUT_DIR/${base}.demultiplexed -lf TRUE -gzip FALSE \> _condition_uncompressedtext_output_$OUT_DIR/${demultiplex_moniker}.stdout 2\> _condition_uncompressedtext_output_$OUT_DIR/${demultiplex_moniker}.stderr
# for each distinct sample , combine all the slices 
# get the distinct samples
for outfile in tardis_*/\${base}.*.demultiplexed/*.fastq; do
   sample=\`basename \$outfile\`
   echo \$sample >> $OUT_DIR/\${base}.demultiplexed/sample_list
done

# combine all slices 
for sample in \`cat $OUT_DIR/\${base}.demultiplexed/sample_list\`; do
   cat tardis_*/\${base}.*.demultiplexed/\${sample}  > $OUT_DIR/\${base}.demultiplexed/\${sample}
done
END_SPLIT
         else
            cat << END_NOSPLIT > $script
#!/bin/bash
#
# note , currently using -k option for debugging - remove this
#
set -x
base=`basename $file`
mkdir ${OUT_DIR}/${base}.demultiplexed
cd ${OUT_DIR}
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR java -jar $SEQ_PRISMS_BIN/../bin/GBSX_v1.3.jar --Demultiplexer $ENZYME_PHRASE -f1 $file -i $OUT_DIR/$sample_info_base  -o $OUT_DIR/${base}.demultiplexed -lf TRUE -gzip TRUE \> $OUT_DIR/${demultiplex_moniker}.stdout 2\> $OUT_DIR/${demultiplex_moniker}.stderr
END_NOSPLIT
         fi
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
   make -f demultiplex_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_DIR/demultiplex_targets.txt` > $OUT_DIR/demultiplex_prism.log 2>&1

   # run summaries
}

function html_prism() {
   echo "tba" > $OUT_DIR/demultiplex_prism.html 2>&1
}

function clean() {
   if [ -f $OUT_DIR/tardis.toml.orig  ]; then
      mv $OUT_DIR/tardis.toml.orig $OUT_DIR/tardis.toml
   else 
      echo "warning  - did not find $OUT_DIR/tardis.toml.orig to restore, check that $OUT_DIR/tardis.toml is what you want"
   fi
   nohup rm -rf $OUT_DIR/tardis_* > $OUT_DIR/demultiplex_clean.log 2>&1 &
   rm -f $OUT_DIR/*.fastq
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
         echo "error state from demultiplex  run - skipping html page generation and clean-up"
         exit 1
      fi
   fi
}


set -x
main "$@"
set +x
