#!/bin/bash
#
# this prism supports a basic q/c gbs analysis, of data that is assumed to be 
# generated and hosted by AgResearch  - i.e. there are dependencies on the 
# database etc. It assumes that the demultiplex prism has been run.
# 
#

declare -a files_array

function get_opts() {

   DRY_RUN=no
   DEBUG=no
   HPC_TYPE=slurm
   FILES=""
   OUT_ROOT=""
   FORCE=no
   ENGINE=KGD_tassel3
   ANALYSIS=all

   help_text="
usage :\n 
./ag_gbs_qc_prism.sh  [-h] [-n] [-d] [-f] [-C hpctype] [-a demultiplex|kgd|fasta_sample|kmer_analysis|blast_analysis|bwa_mapping|all] -O outdir -r run cohort [.. cohort] \n
example:\n
./ag_gbs_qc_prism.sh -n -O /dataset/hiseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI  SQ2745.all.PstI.PstI  SQ2746.all.PstI.PstI  SQ0756.all.DEER.PstI  SQ0756.all.GOAT.PstI  SQ2743.all.PstI-MspI.PstI-MspI \n
./ag_gbs_qc_prism.sh -n -f -O /dataset/hiseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI SQ2745.all.PstI.PstI SQ2746.all.PstI.PstI SQ0756.all.DEER.PstI SQ0756.all.GOAT.PstI SQ2743.all.PstI-MspI.PstI-MspI\n
./ag_gbs_qc_prism.sh -n -f -C local -O /dataset/hiseq/scratch/postprocessing/gbs/180718_D00390_0389_ACCRDYANXX -r 180718_D00390_0389_ACCRDYANXX SQ2744.all.PstI-MspI.PstI-MspI SQ2745.all.PstI.PstI SQ2746.all.PstI.PstI SQ0756.all.DEER.PstI SQ0756.all.GOAT.PstI SQ2743.all.PstI-MspI.PstI-MspI \n
./ag_gbs_qc_prism.sh -n -f  -a kmer_analysis -O /dataset/gseq_processing/scratch/gbs/180824_D00390_0394_BCCPYFANXX -r 180824_D00390_0394_BCCPYFANXX SQ0784.all.DEER.PstI \n
"
   while getopts ":nhfO:C:r:a:" opt; do
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
       r)
         RUN=$OPTARG
         ;;
       a)
         ANALYSIS=$OPTARG
         ;;
       C)
         HPC_TYPE=$OPTARG
         ;;
       O)
         OUT_ROOT=$OPTARG
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

   COHORT_STRING=$@

   # this is needed because of the way we process args a "$@" - which
   # is needed in order to parse parameter sets to be passed to the
   # aligner (which are space-separated)
   declare -a cohorts="(${COHORT_STRING})";
   NUM_COHORTS=${#cohorts[*]}
   for ((i=0;$i<$NUM_COHORTS;i=$i+1)) do
      cohorts_array[$i]=${cohorts[$i]}
   done

}


function check_opts() {
   if [ -z "$SEQ_PRISMS_BIN" ]; then
      echo "please set SEQ_PRISMS_BIN environment variable"
      exit 1
   fi

   if [ -z "$GBS_PRISM_BIN" ]; then
      echo "please set GBS_PRISM_BIN environment variable"
      exit 1
   fi

   if [ ! -d $OUT_ROOT ]; then
      echo "out_dir $OUT_ROOT not found"
      exit 1
   fi

   if [[ $HPC_TYPE != "local" && $HPC_TYPE != "slurm" ]]; then
      echo "HPC_TYPE must be one of local, slurm"
      exit 1
   fi

   if [[ ( $ENGINE != "KGD_tassel3" ) ]] ; then
      echo "gbs engines supported : KGD_tassel3 (not $ENGINE ) "
      exit 1
   fi

   if [[ ( $ANALYSIS != "all" ) && ( $ANALYSIS != "demultiplex" ) && ( $ANALYSIS != "kgd" ) && ( $ANALYSIS != "fasta_sample" ) && ( $ANALYSIS != "kmer_analysis" ) && ( $ANALYSIS != "blast_analysis" && ( $ANALYSIS != "taxonomy_analysis" )  && ( $ANALYSIS != "bwa_mapping" ) ) ]] ; then
      echo "analysis must be one of all, demultiplex, kgd , kmer_analysis, blast_analysis ) "
      exit 1
   fi

}

function echo_opts() {
  echo OUT_ROOT=$OUT_ROOT
  echo DRY_RUN=$DRY_RUN
  echo DEBUG=$DEBUG
  echo HPC_TYPE=$HPC_TYPE
  echo COHORTS=${cohorts_array[*]}
  echo ENGINE=$ENGINE
  echo ANALYSIS=$ANALYSIS

}


#
# edit this method to set required environment (or set up
# before running this script)
#
function configure_env() {
   export CONDA_ENVS_PATH=$CONDA_ENVS_PATH:/dataset/bioinformatics_dev/active/conda-env
   cd $GBS_PRISM_BIN
   cp ag_gbs_qc_prism.sh $OUT_ROOT
   cp ag_gbs_qc_prism.mk $OUT_ROOT
   cp demultiplex_prism.sh $OUT_ROOT
   cp genotype_prism.sh $OUT_ROOT
   cp get_reads_tags_per_sample.py $OUT_ROOT

   echo "
max_tasks=50
" > $OUT_ROOT/tardis.toml

   echo "
conda activate bifo-essential
" > $OUT_ROOT/bifo-essential_env.inc

   echo "
export CONDA_ENVS_PATH=$CONDA_ENVS_PATH
conda activate bioconductor
" > $OUT_ROOT/configure_bioconductor_env.src



   echo "
conda activate /dataset/gseq_processing/active/bin/gbs_prism/conda/gbs_prism 
" > $OUT_ROOT/gbs_prism_env.inc

   cd $OUT_ROOT
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
   # for each cohort make a target moniker  and write associated
   # wrapper, which will be called by make

   rm -f $OUT_ROOT/*_targets.txt

   for ((j=0;$j<$NUM_COHORTS;j=$j+1)) do
      cohort=${cohorts_array[$j]}
      cohort_moniker=${RUN}.$cohort

      # extract keyfile and unblinding script for this cohort
      # cohort is like SQ0756.all.DEER.PstI
      libname=`echo $cohort | awk -F\. '{print $1}' -`
      qc_cohort=`echo $cohort | awk -F\. '{print $2}' -`
      gbs_cohort=`echo $cohort | awk -F\. '{print $3}' -`
      enzyme=`echo $cohort | awk -F\. '{print $4}' -`
      fcid=`echo $RUN | awk -F_ '{print substr($4,2)}' -`


      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t qc > $OUT_ROOT/${cohort_moniker}.key
      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t unblind_script  > $OUT_ROOT/${cohort_moniker}.unblind.sed
      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t files  > $OUT_ROOT/${cohort_moniker}.filenames
      $GBS_PRISM_BIN/list_keyfile.sh -s $libname -f $fcid -e $enzyme -g $gbs_cohort -q $qc_cohort -t bwa_index_paths > $OUT_ROOT/${cohort_moniker}.bwa_references
      adapter_to_cut=`$GBS_PRISM_BIN/get_processing_parameters.py --parameter_file $OUT_ROOT/SampleProcessing.json --parameter_name adapter_to_cut`
      bwa_alignment_parameters=`$GBS_PRISM_BIN/get_processing_parameters.py --parameter_file $OUT_ROOT/SampleProcessing.json --parameter_name bwa_alignment_parameters`

      for analysis_type in all bwa_mapping demultiplex kgd kmer_analysis blast_analysis fasta_sample taxonomy_analysis; do
         echo $OUT_ROOT/$cohort_moniker.$analysis_type  >> $OUT_ROOT/${analysis_type}_targets.txt
         script=$OUT_ROOT/${cohort_moniker}.${analysis_type}.sh
         if [ -f $script ]; then
            if [ ! $FORCE == yes ]; then
               echo "found existing gbs script $script  - will re-use (use -f to force rebuild of scripts) "
               continue
            fi
         fi
      done

      ############### demultiplex script
      echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort
# run demultiplexing
./demultiplex_prism.sh -C $HPC_TYPE -x tassel3_qc -l $OUT_ROOT/${cohort_moniker}.key  -e $enzyme -O $OUT_ROOT/$cohort \`cat $OUT_ROOT/${cohort_moniker}.filenames | awk '{print \$2}' -\` 
if [ \$? != 0 ]; then
   echo \"warning demultiplex of $OUT_ROOT/${cohort_moniker}.key returned an error code\"
   exit 1
fi
# summarise the tag counts
cat $cohort/*.FastqToTagCount.stdout | ./get_reads_tags_per_sample.py > $cohort/TagCount.csv
      " > $OUT_ROOT/${cohort_moniker}.demultiplex.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.demultiplex.sh

     ################ kgd script
     echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort
# run genotyping
./genotype_prism.sh -C $HPC_TYPE -x KGD_tassel3 $OUT_ROOT/$cohort
if [ \$? != 0 ]; then
   echo \"warning , genotyping of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
# generate unblinded output
for file in  $OUT_ROOT/$cohort/TagCount.csv $OUT_ROOT/$cohort/${cohort}.KGD_tassel3.KGD.stdout $OUT_ROOT/$cohort/KGD/HeatmapOrderHWdgm.05.csv $OUT_ROOT/$cohort/KGD/HighRelatedness.csv $OUT_ROOT/$cohort/KGD/HighRelatednessHWdgm.05.csv $OUT_ROOT/$cohort/KGD/SampleStats.csv $OUT_ROOT/$cohort/KGD/seqID.csv ; do
   if [ -f \$file ]; then
      cp -p \$file \$file.blinded
      cat \$file.blinded | sed -f $OUT_ROOT/${cohort_moniker}.unblind.sed > \$file
   fi
done
     " >  $OUT_ROOT/${cohort_moniker}.kgd.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.kgd.sh 

     ################ fasta_sample script (i.e. samples tags)
     echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort/fasta_small_lowdepthsample
mkdir -p $cohort/fasta_medium_lowdepthsample
# run fasta_sample
# sample high coverage - not running currently 
# sample low coverage 
$SEQ_PRISMS_BIN/sample_prism.sh  -a tag_count_unique -t 2 -T 10 -s .002 -O $OUT_ROOT/$cohort/fasta_small_lowdepthsample $OUT_ROOT/$cohort/tagCounts/*.cnt
$SEQ_PRISMS_BIN/sample_prism.sh  -a tag_count_unique -t 2 -T 10 -s .05 -O $OUT_ROOT/$cohort/fasta_medium_lowdepthsample $OUT_ROOT/$cohort/tagCounts/*.cnt

if [ \$? != 0 ]; then
   echo \"warning , fasta sample of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.fasta_sample.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.fasta_sample.sh 


     ################ blast script 
     echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort/blast
# run blast
$SEQ_PRISMS_BIN/align_prism.sh -m 60 -a blastn -r nt -p \"-evalue 1.0e-10  -dust \\'20 64 1\\' -max_target_seqs 1 -outfmt \\'7 qseqid sseqid pident evalue staxids sscinames scomnames sskingdoms stitle\\'\" -O $OUT_ROOT/$cohort/blast $OUT_ROOT/$cohort/fasta_small_lowdepthsample/*.fasta
if [ \$? != 0 ]; then
   echo \"warning , blast  of $OUT_ROOT/$cohort/fasta_small_lowdepthsample returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.blast_analysis.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.blast_analysis.sh


     ################ taxonomy summary script 
     echo "#!/bin/bash
cd $OUT_ROOT
# summarise blast results 
$SEQ_PRISMS_BIN/taxonomy_prism.sh -w tag_count -a "Overview-$cohort" -O $OUT_ROOT/$cohort/blast $OUT_ROOT/$cohort/blast/*.results.gz  
if [ \$? != 0 ]; then
   echo \"warning, summary of $OUT_ROOT/$cohort/blast returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.taxonomy_analysis.sh 
      chmod +x $OUT_ROOT/${cohort_moniker}.taxonomy_analysis.sh 


     ################ low-depth kmer summary script
     echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort/kmer_analysis
$SEQ_PRISMS_BIN/kmer_prism.sh -a fasta -p \"-k 6 --weighting_method tag_count\" -O $OUT_ROOT/$cohort/kmer_analysis $OUT_ROOT/$cohort/fasta_medium_lowdepthsample/*.fasta 
if [ \$? != 0 ]; then
   echo \"warning, kmer analysis of $OUT_ROOT/$cohort/fasta_medium_lowdepthsample returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.kmer_analysis.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.kmer_analysis.sh


     ################ bwa mapping script (includes sampling and trimming)
     echo "#!/bin/bash
cd $OUT_ROOT
mkdir -p $cohort/bwa_mapping
#
# sample each file referred to in $OUT_ROOT/${cohort_moniker}.filenames
#$SEQ_PRISMS_BIN/sample_prism.sh  -s .00005 -M 15000 -a fastq -O $OUT_ROOT/$cohort/bwa_mapping  \`cut -f 2 $OUT_ROOT/${cohort_moniker}.filenames\`   
#if [ \$? != 0 ]; then
#   echo \"warning, bwa mapping of $OUT_ROOT/$cohort returned an error code\"
#   exit 1
#fi
# trim the samples 
#for fastq_sample in $cohort/bwa_mapping/*.fastq.gz; do
#   outbase=\`basename \$fastq_sample .fastq.gz \`
#   tardis -d $OUT_ROOT/$cohort/bwa_mapping --hpctype $HPC_TYPE --shell-include-file $OUT_ROOT/bifo-essential_env.inc cutadapt -f fastq -a $adapter_to_cut \$fastq_sample \> $OUT_ROOT/$cohort/bwa_mapping/\$outbase.trimmed.fastq 2\>$OUT_ROOT/$cohort/bwa_mapping/\$outbase.trimmed.report
#   if [ \$? != 0 ]; then
#      echo \"warning, cutadapt of \$fastq_sample returned an error code\"
#      exit 1
#   fi
#done

# align the trimmed samples to the references referred to in $OUT_ROOT/${cohort_moniker}.bwa_references
cut -f 2 $OUT_ROOT/$cohort_moniker.bwa_references > $OUT_ROOT/$cohort/bwa_mapping/references.txt
$SEQ_PRISMS_BIN/align_prism.sh -m 60 -a bwa -r $OUT_ROOT/$cohort/bwa_mapping/references.txt -p \"$bwa_alignment_parameters\" -O $OUT_ROOT/$cohort/bwa_mapping -C $HPC_TYPE $OUT_ROOT/$cohort/bwa_mapping/*.trimmed.fastq
if [ \$? != 0 ]; then
   echo \"warning, bwa mapping of $OUT_ROOT/$cohort returned an error code\"
   exit 1
fi
     " >  $OUT_ROOT/${cohort_moniker}.bwa_mapping.sh
      chmod +x $OUT_ROOT/${cohort_moniker}.bwa_mapping.sh
   done
}



function fake_prism() {
   echo "dry run ! 

   "
   exit 0
}

function run_prism() {
   cd $OUT_ROOT

   make -f ag_gbs_qc_prism.mk -d -k  --no-builtin-rules -j 16 `cat $OUT_ROOT/${ANALYSIS}_targets.txt` > $OUT_ROOT/${ANALYSIS}.log 2>&1

   # run summaries
}

function html_prism() {
   mkdir -p $OUT_ROOT/html

   # summarise bwa mappings 
   if [ ! -f $OUT_ROOT/html/mapping_stats.jpg ]; then 
       tardis -d $OUT_ROOT/html $GBS_PRISM_BIN/collate_mapping_stats.py $OUT_ROOT/*/bwa_mapping/*.stats \> $OUT_ROOT/html/bwa_stats_summary.txt
       tardis -d $OUT_ROOT/html --shell-include-file $OUT_ROOT/configure_bioconductor_env.src Rscript --vanilla  $GBS_PRISM_BIN/mapping_stats_plots.r datafolder=$OUT_ROOT/html
   fi
}

function clean() {
   echo "cleaning up tardis working folders..."
   find $OUT_ROOT -name "tardis_*" -type d -exec rm {} \;
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
