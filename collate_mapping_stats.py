#!/bin/env python 
import sys
import re
import os

bam_stats_files=sys.argv[1:]
stats_dict={}

example= """
16182 + 0 in total (QC-passed reads + QC-failed reads)
0 + 0 secondary
0 + 0 supplementary
0 + 0 duplicates
6011 + 0 mapped (37.15% : N/A)
0 + 0 paired in sequencing
0 + 0 read1
0 + 0 read2
0 + 0 properly paired (N/A : N/A)
0 + 0 with itself and mate mapped
0 + 0 singletons (N/A : N/A)
0 + 0 with mate mapped to a different chr
0 + 0 with mate mapped to a different chr (mapQ>=5)
"""

for filename in bam_stats_files:
   # e.g. SQ0788_CCVK0ANXX_s_1_fastq.txt.gz.fastq.s.00005.trimmed.fastq.bwa.CELA_all_but_U.fa.B10.stats
   # containing e.g.
   #Mapped reads:      260087	(70.3575%)
   #Forward strand:    239494	(64.7868%)
   #Reverse strand:    130171	(35.2132%)
   #print "DEBUG : processing %s"%filename
   sample_ref = re.sub("\.txt\.gz\.fastq\.s\.\d+\.trimmed\.fastq\.bwa","",os.path.basename(filename))
   sample_ref = re.sub("\.B10\.stats","",sample_ref)

   map_stats = [0,0,0] # will contain count, total, percent
   
   with open(filename,"r") as f:     
      for record in f:
         tokens = re.split("\s+", record.strip())
         #print tokens
         if len(tokens) >= 5:
            if (tokens[3],tokens[4])  == ("in", "total"):
               map_stats[1] = float(tokens[0]) 
            elif tokens[3] == "mapped":
               map_stats[0] = float(tokens[0]) 
               map_stats[2] = map_stats[0]/map_stats[1] 
               break

   stats_dict[sample_ref] = map_stats

print "\t".join(("sample_ref", "map_pct", "map_std"))
for sample_ref in stats_dict:
   out_rec = [sample_ref,"0","0"]

   (p,n) = (stats_dict[sample_ref][2], stats_dict[sample_ref][1])

   q = 1-p
   if n>0:
      stddev = (p * q / n ) ** .5
   out_rec[1] = str(p*100.0)
   out_rec[2] = str(stddev*100.0)
   print "\t".join(out_rec)
                               
                               

   

               
                    
            
                    
                    
         
        
                    
