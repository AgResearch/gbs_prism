#!/bin/sh


#example : 
#$SEQ_PRISMS_BIN/../make_combined_tags.sh qc271846-2_merged_X3.cnt	qc271891-2_merged_X3.cnt	qc271926-2_merged_X3.cnt	qc271909-2_merged_X3.cnt	qc271922-2_merged_X3.cnt	qc271915-2_merged_X3.cnt	qc271845-2_merged_X3.cnt	qc271893-2_merged_X3.cnt	qc271853-2_merged_X3.cnt	qc271850-2_merged_X3.cnt	qc271848-2_merged_X3.cnt	qc271872-2_merged_X3.cnt	qc271902-2_merged_X3.cnt	qc271844-2_merged_X3.cnt	qc271890-2_merged_X3.cnt	qc271934-2_merged_X3.cnt	qc271886-2_merged_X3.cnt	qc271875-2_merged_X3.cnt

TEMP=/dataset/hiseq/scratch/postprocessing/180611_D00390_0369_ACCJKKANXX.gbs/SQ2708.processed_sample/uneak/annotation

rm  -f $TEMP/_next $TEMP/_total $TEMP/_total1

for tag_file in "$@"; do
   if [ ! -f $TEMP/_total ]; then
      $SEQ_PRISMS_BIN/cat_tag_count.sh $tag_file > $TEMP/_total
      continue
   fi

   $SEQ_PRISMS_BIN/cat_tag_count.sh $tag_file > $TEMP/_next

   $SEQ_PRISMS_BIN/../add_tags.py $TEMP/_total $TEMP/_next > $TEMP/_total1
   mv $TEMP/_total1 $TEMP/_total
done


cat $TEMP/_total

rm  $TEMP/_next $TEMP/_total 
