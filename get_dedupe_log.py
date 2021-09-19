#!/bin/env python
from __future__ import print_function
import sys
import re
import os

fastq_links=sys.argv[1:]
# e.g.
#/dataset/hiseq/scratch/postprocessing/gbs/210823_A01439_0016_BHHYF5DRXY/SQ1671.all.PstI-MspI.PstI-MspI/Illumina/SQ1671_HHYF5DRXY_s_1_fastq.txt.gz
#/dataset/hiseq/scratch/postprocessing/gbs/210823_A01439_0016_BHHYF5DRXY/SQ1671.all.PstI-MspI.PstI-MspI/Illumina/SQ1671_HHYF5DRXY_s_2_fastq.txt.gz

stats_dict={}

example= """
Total number of reads in lane=243469299
Total number of good barcoded reads=199171115
"""

for linkname in fastq_links:
   r=os.path.realpath(linkname)
   #print r

   logname = os.path.join(os.path.dirname(r), "%s.stderr"%(os.path.basename(r)))
   stats_dict[logname] = None

   if not os.path.isfile(logname):
      print("unable to find logfile: %s"%logname,file=sys.stderr)
      continue

   stats_dict[logname] = {"linkname" : os.path.basename(linkname)}


   # look for
   #Reads In:            153880133
   #Clumps Formed:        12860564
   #Duplicates Found:     34074564
   #Reads Out:           119805569
   with open(logname,"r") as l:
      for record in l:
         for key in ("Reads In","Duplicates Found","Reads Out"):
            if re.match("^%s:"%key, record) is not None:
               fields=re.split("\s+",record.strip())
               stats_dict[logname][key] = int(fields[-1])

total_in=0
total_dups=0
for logname in stats_dict:
   if stats_dict[logname] is None:
      print("%(linkname)s: unavailable %"%stats_dict[logname])
      continue
      
   stats_dict[logname]["percent"] = 100.0 *  stats_dict[logname]["Duplicates Found"]/stats_dict[logname]["Reads In"]
   total_in += stats_dict[logname]["Reads In"]
   total_dups += stats_dict[logname]["Duplicates Found"]
   
   print("%(linkname)s: in=%(Reads In)s duplicates=%(Duplicates Found)s ( %(percent)4.1f%% ) "%stats_dict[logname])

print("\n")
print("Total: in=%s duplicates=%s ( %4.1f%% ) "%(total_in, total_dups, 100.0 * total_dups/total_in))



                               
                               

   

               
                    
            
                    
                    
         
        
                    
