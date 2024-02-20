#!/bin/sh

for file in `ls .`; do
   if [ -f $file ]; then
      #echo $file
      refs=`grep $file * 2>/dev/null`
      if [ -z "$refs" ]; then
         echo "$file not referenced"
      fi
   fi
done
