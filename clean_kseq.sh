#!/bin/bash
#
# this is a work around for a bug in a couple of scripts associated with the gbs pipelines
# which create temp files on application / login servers but do not clean up
# it is run inside a screen session
#

set -x

while [ 1 ]; do
   if [ -f kseq_to_delete.txt ]; then
      rm `cat kseq_to_delete.txt`
   fi
   ls /tmp/kseq_count* > kseq_to_delete.txt 2>/dev/null
   ls /tmp/listDBKeyfile* >> kseq_to_delete.txt 2>/dev/null
   if [ $? != 0 ]; then
      echo "removing kseq_to_delete.txt"
      rm kseq_to_delete.txt
   fi
   sleep 60
done
