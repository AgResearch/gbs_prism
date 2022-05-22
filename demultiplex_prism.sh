#!/bin/bash
#
# this prism supports demultiplex of a set of sequence files , all of which contain
# multiplexed GBS sequencing data as specified by a sample information file.
# 
#

# references : 
#
# https://biohpc.cornell.edu/lab/doc/TasselPipelineGBS20120215.pdf

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
   PARAMETERS_FILE=""
   

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
   while getopts ":nhSfO:C:x:l:e:p:" opt; do
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
       p)
         PARAMETERS_FILE=$OPTARG
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
      else
         # map enzymes such as HpaIII and HpaII (methylation sensitive) to equivalent
         # (same recognition-site) enzymes that uneak knows about 
         enzyme_for_uneak=$ENZYME_INFO
         echo $enzyme_for_uneak | grep -iq "hpa" > /dev/null 2>&1
         if [ $? == 0 ]; then
            echo "attempting to map enzyme $ENZYME_INFO to an equivalent for uneak..."
            enzyme_for_uneak=`echo $ENZYME_INFO | sed -r 's/HpaII|HpaIII/MspI/g' -`
            if [ $ENZYME_INFO != $enzyme_for_uneak ]; then
               echo "$ENZYME_INFO mapped to $enzyme_for_uneak for uneak"
            else
               echo "warning, no mapping done so will use $ENZYME_INFO"
            fi
         fi
      fi
   elif [[  ( $ENGINE == "tassel3" ) || ( $ENGINE == "tassel3_qc" ) ]]; then
      echo "must specify enzyme , for tassel3 (should match enzyme specified in keyfile)"
      exit 1
   fi
   if [ ! -z "$PARAMETERS_FILE" ]; then
      if [ ! -f "$PARAMETERS_FILE" ]; then
         echo "could not find $PARAMETERS_FILE"
         exit 1
      fi
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
  echo PARAMETERS_FILE=$PARAMETERS_FILE
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
   if [ -f $ENZYME_INFO ]; then
      cp $ENZYME_INFO $OUT_DIR
   fi
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
   cp $GBS_PRISM_BIN/etc/larger_mem_slurm_array_job $OUT_DIR
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

function get_uneak_plugin_parameters() {
   if [ -z "$PARAMETERS_FILE" ]; then
      uneak_plugin_parameters=""
   else
      plugin_name=$1
      uneak_plugin_parameters=`grep $plugin_name $PARAMETERS_FILE | sed "s/$plugin_name//g" -`
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

         # get plugin parameters (if applicable)
         get_uneak_plugin_parameters FastqToTagCount ; p_FastqToTagCount=$uneak_plugin_parameters
         get_uneak_plugin_parameters MergeTaxaTagCount ; p_MergeTaxaTagCount=$uneak_plugin_parameters
         get_uneak_plugin_parameters TagCountToTagPair ; p_TagCountToTagPair=$uneak_plugin_parameters
         get_uneak_plugin_parameters TagPairToTBT ; p_TagPairToTBT=$uneak_plugin_parameters
         get_uneak_plugin_parameters TBTToMapInfo ; p_TBTToMapInfo=$uneak_plugin_parameters
         get_uneak_plugin_parameters MapInfoToHapMap ; p_MapInfoToHapMap=$uneak_plugin_parameters

         # 
         # note that the tassel3 modules do not generally exit with a non-zero error code 
         # if something goes wrong , so the code below that looks at the exit code does not work 
         # - even if an early module fails , all modules are attempted , and the 
         # error status is only picked up downstream when something tries to use the 
         # demultiplex result.  This needs to be improved - e.g. sniff the stdout / stderr files 
         # from these modules to figure out if the job completed OK - then exit with the 
         # appropiate code
         # 

         echo "#!/bin/bash
cd $OUT_DIR  
if [ ! -f tagCounts.done ]; then 
   mkdir tagCounts 
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src run_pipeline.pl -Xms512m -Xmx5g -fork1 -UFastqToTagCountPlugin -p $p_FastqToTagCount -w ./ -c 1 -e $enzyme_for_uneak  -s 400000000 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stdout 2\>$OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from FastqToTagCount process - quitting\"; exit 1
else
   date > tagCounts.done
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

         # get plugin parameters (if applicable)
         get_uneak_plugin_parameters FastqToTagCount ; p_FastqToTagCount=$uneak_plugin_parameters
         get_uneak_plugin_parameters MergeTaxaTagCount ; p_MergeTaxaTagCount=$uneak_plugin_parameters
         get_uneak_plugin_parameters TagCountToTagPair ; p_TagCountToTagPair=$uneak_plugin_parameters
         get_uneak_plugin_parameters TagPairToTBT ; p_TagPairToTBT=$uneak_plugin_parameters
         get_uneak_plugin_parameters TBTToMapInfo ; p_TBTToMapInfo=$uneak_plugin_parameters
         get_uneak_plugin_parameters MapInfoToHapMap ; p_MapInfoToHapMap=$uneak_plugin_parameters

         echo "#!/bin/bash
cd $OUT_DIR  
if [ ! -f tagCounts.done ]; then 
   mkdir tagCounts 
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src run_pipeline.pl -Xms512m -Xmx5g -fork1 -UFastqToTagCountPlugin $p_FastqToTagCount -w ./ -c 1 -e $enzyme_for_uneak  -s 400000000 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stdout 2\>$OUT_DIR/${demultiplex_moniker}.FastqToTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from FastqToTagCount process - quitting\"; exit 1
else
   date > tagCounts.done
fi

if [ ! -f mergedTagCounts.done ]; then 
   mkdir mergedTagCounts
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UMergeTaxaTagCountPlugin $p_MergeTaxaTagCount -w ./ -m 600000000 -x 100000000 -c 5 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.MergeTaxaTagCount.stdout  2\>$OUT_DIR/${demultiplex_moniker}.MergeTaxaTagCount.stderr
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from MergeTaxaTagCount process - quitting\"; exit 2
else
   date > mergedTagCounts.done 
fi

if [ ! -f tagPair.done ]; then 
   mkdir tagPair
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTagCountToTagPairPlugin $p_TagCountToTagPair -w ./ -e 0.03 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.TagCountToTagPair.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TagCountToTagPair.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TagCountToTagPair process - quitting\"; exit 3
else
   date > tagPair.done
fi

if [ ! -f tagsByTaxa.done ]; then 
   mkdir tagsByTaxa
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTagPairToTBTPlugin $p_TagPairToTBT -w ./ -endPlugin -runfork1  \> $OUT_DIR/${demultiplex_moniker}.TagPairToTBT.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TagPairToTBT.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TagPairToTBT process - quitting\"; exit 4
else
   date > tagsByTaxa.done
fi

if [ ! -f mapInfo.done ] ; then 
   mkdir mapInfo
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UTBTToMapInfoPlugin $p_TBTToMapInfo -w ./ -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.TBTToMapInfo.stdout  2\>$OUT_DIR/${demultiplex_moniker}.TBTToMapInfo.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from TBTToMapInfo process - quitting\"; exit 5
else
   date > mapInfo.done
fi

if [ ! -f hapMap.done ]; then
   mkdir hapMap
   tardis --hpctype $HPC_TYPE -k -d $OUT_DIR --shell-include-file $OUT_DIR/tassel3_env.src	run_pipeline.pl -Xms512m -Xmx500g -fork1 -UMapInfoToHapMapPlugin $p_MapInfoToHapMap -w ./ -mnMAF 0.03 -mxMAF 0.5 -mnC 0.1 -endPlugin -runfork1 \> $OUT_DIR/${demultiplex_moniker}.MapInfoToHapMap.stdout  2\>$OUT_DIR/${demultiplex_moniker}.MapInfoToHapMap.stderr 
fi
if [ \$? != 0 ]; then
   echo \"demultplex_prism.sh: error code returned from MapInfoToHapMap process - quitting\"; exit 6
else
   date > hapMap.done
fi

if [ ! -f hapMap.done ]; then
   echo \"demultplex_prism.sh: didn't find hapMap.done - something went wrong - quitting\"; exit 7
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
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR java -jar $SEQ_PRISMS_BIN/../bin/GBSX_v1.3.jar --Demultiplexer $ENZYME_PHRASE -f1 _condition_fastq_input_$file -i $OUT_DIR/$sample_info_base  -o _condition_output_$OUT_DIR/${base}.demultiplexed -lf TRUE -gzip FALSE -mb 0 -me 0 -n false -t 8 \> _condition_uncompressedtext_output_$OUT_DIR/${demultiplex_moniker}.stdout 2\> _condition_uncompressedtext_output_$OUT_DIR/${demultiplex_moniker}.stderr
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
            # see if file is compressed  and set gzip option
            gzip_phrase="-gzip TRUE"
            gunzip -qt $file > /dev/null 2>&1
            if [ $? != 0 ]; then
               gzip_phrase=""
            fi
            
            cat << END_NOSPLIT > $script
#!/bin/bash
#
# note , currently using -k option for debugging - remove this
#
set -x
base=`basename $file`
mkdir ${OUT_DIR}/${base}.demultiplexed
cd ${OUT_DIR}
tardis --hpctype $HPC_TYPE -k -d $OUT_DIR java -jar $SEQ_PRISMS_BIN/../bin/GBSX_v1.3.jar --Demultiplexer $ENZYME_PHRASE -f1 $file -i $OUT_DIR/$sample_info_base  -o $OUT_DIR/${base}.demultiplexed -lf TRUE $gzip_phrase -mb 0 -me 0 -n false -t 8 \> $OUT_DIR/${demultiplex_moniker}.stdout 2\> $OUT_DIR/${demultiplex_moniker}.stderr
END_NOSPLIT
         fi
         chmod +x $script
      fi
   done 

}

function fake() {
   echo "dry run ! 

   "
   exit 0
}

function run() {
   make -f demultiplex_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_DIR/demultiplex_targets.txt` > $OUT_DIR/demultiplex_prism.log 2>&1

   # run summaries
}

function html() {
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
      fake
   else
      run
      if [ $? == 0 ] ; then
         html
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
