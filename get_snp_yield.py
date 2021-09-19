#!/bin/env python 
import sys
import re
import os

FastqToTagCount_stdout=sys.argv[1]  # e.g. /dataset/gseq_processing/scratch/gbs/200626_D00390_0557_ACECFLANXX/SQ1345.all.cattle.PstI/200626_D00390_0557_ACECFLANXX.SQ1345.all.cattle.PstI.key.PstI.tassel3_qc.FastqToTagCount.stdout
HapMap_hmc=sys.argv[2] # e.g. /dataset/gseq_processing/scratch/gbs/200626_D00390_0557_ACECFLANXX/SQ1345.all.cattle.PstI/hapMap/HapMap.hmc.txt

read_count = 0
with open(FastqToTagCount_stdout,"r") as f:     
   for record in f:
      hit=re.search("^Total number of good barcoded reads=(\d+)$", record.strip())
      if hit is not None:
         read_count +=float(hit.groups()[0])

snp_count=0
with open(HapMap_hmc,"r") as f:
   for record in f:
      snp_count += 1

snp_count -= 1

if read_count > 0:
   print "%d SNPs<br/> %d good barcoded reads <br/> (%7.3f%%)"%(snp_count, read_count, 100 * ( snp_count / read_count ))
else:
   print "read count zero !" 
   

               
                    
            
                    
                    
         
        
                    
