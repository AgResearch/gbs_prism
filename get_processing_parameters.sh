#!/bin/bash

function get_processing_parameters() {

   OUTPUT_ROOT=$1_

   PARAMETERS_FILE=$OUTPUT_ROOT/SampleProcessing.json
   if [ -f $PARAMETERS_FILE ]; then
      answer=n
      echo "found existing processing parameters file $OUTPUT_ROOT/SampleProcessing.json  - is it OK to update this with GBS settings ? (y/n, default=n)"
      read answer

      if [ "$answer" != "y" ]; then
         echo "OK will not update"
      else
         echo "OK will update, saving previous as $OUTPUT_ROOT/SampleProcessing.json.old"
         mv $OUTPUT_ROOT/SampleProcessing.json $OUTPUT_ROOT/SampleProcessing.json.old
         PARAMETERS_FILE=""
      fi
   else
      PARAMETERS_FILE=""
   fi

   if [ -z "$PARAMETERS_FILE" ]; then
      # tardis --local used so not queued
      echo "compiling processing parameters file $OUTPUT_ROOT/SampleProcessing.json . . .

      "
      tardis -d $OUTPUT_ROOT --hpctype local $GBS_PRISM_BIN/get_processing_parameters.py --json_out_file $OUTPUT_ROOT/SampleProcessing.json --parameter_file $SAMPLE_SHEET --species_references_file  /dataset/hiseq/active/sample-sheets/reference_genomes.csv
   fi

   if [ ! -f "$OUTPUT_ROOT/SampleProcessing.json" ]; then
      echo "error , failed creating parameters files $OUTPUT_ROOT/SampleProcessing.json"
      exit 1
   else
      PARAMETERS_FILE=$OUTPUT_ROOT/SampleProcessing.json
   fi


   echo "will use the following processing parameters (press any key for listing)"
   read answer
   more $PARAMETERS_FILE
   echo "

   OK to use these parameters ? (y/n, default=y)
   "
   read answer
   if [ "$answer" == "n" ]; then
      echo "please edit $PARAMETERS_FILE and try again"
      exit 1
   fi
}

if [ ! -d "$1" ]; then
   echo "output root $1 does not exist"
   exit 1
fi

if [ -z "$GBS_PRISM_BIN" ]; then
   echo GBS_PRISM_BIN not set - exiting"
   exit 1
fi

get_processing_parameters($1)


