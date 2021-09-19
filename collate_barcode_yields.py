#!/bin/env python 
import sys
import re
import os

uneak_stdout_files=sys.argv[1:]
stats_dict={}

example= """
Total number of reads in lane=243469299
Total number of good barcoded reads=199171115
"""

for filename in uneak_stdout_files:
   #/dataset/gseq_processing/scratch/gbs/200310_D00390_0538_BCE5FNANXX/SQ1244.all.PstI.PstI/200310_D00390_0538_BCE5FNANXX.SQ1244.all.PstI.PstI.key.PstI.tassel3_qc.FastqToTagCount.stdout
   
   
   sample_ref_tokens = re.split("\.", os.path.basename(filename))[1:]
   sample_ref_match = re.match("^(.*).key",".".join(sample_ref_tokens))
   if sample_ref_match is not None:
      sample_ref = sample_ref_match.groups()[0]
   else:
      sample_ref = "?"

   yield_stats = [0,0] # will contain total reads, total good barcoded
   
   with open(filename,"r") as f:     
      for record in f:
         hit=re.search("^Total number of reads in lane=(\d+)$", record.strip())
         if hit is not None:
            yield_stats[1]+=float(hit.groups()[0])
         hit=re.search("^Total number of good barcoded reads=(\d+)$", record.strip())
         if hit is not None:
            yield_stats[0]+=float(hit.groups()[0])

   stats_dict[sample_ref] = yield_stats

print "\t".join(("sample_ref", "good_pct", "good_std"))
for sample_ref in stats_dict:
   out_rec = [sample_ref,"0","0"]

   n=stats_dict[sample_ref][1]
   if n  > 0:
      p=stats_dict[sample_ref][0]/stats_dict[sample_ref][1]
   else:
      p=0
   
   q = 1-p
   stddev = 0.0
   if n>0:
      stddev = (p * q / n ) ** .5
   out_rec[1] = str(p*100.0)
   out_rec[2] = str(stddev*100.0)
   print "\t".join(out_rec)
                               
                               

   

               
                    
            
                    
                    
         
        
                    
