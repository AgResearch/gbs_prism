#!/bin/env python
from __future__ import print_function

import csv 
import sys
import re
import string
import argparse
import datetime 
import itertools
import os

def parse(options):
   """
   content to be parsed looks like
   
JobID         Start                End                  AllocCPUS   CPUTime
------------  -------------------  -------------------  ----------  ----------
9348079_220   2020-11-27T07:41:29  Unknown              16          16116-19:43:28
9348079_220+  2020-11-27T07:41:30  Unknown              16          16116-19:43:12
14193112      Unknown              Unknown              1           00:00:00
14193242      Unknown              Unknown              1           00:00:00
19375470      2023-08-07T10:01:11  2023-08-07T15:06:05  2           10:09:48
19375470.ba+  2023-08-07T10:01:11  2023-08-07T15:06:06  2           10:09:50
19375470.3    2023-08-07T10:02:35  2023-08-07T15:06:11  1           05:03:36
19386930      2023-08-07T10:01:11  2023-08-07T12:55:22  4           11:36:44
19386930.ba+  2023-08-07T10:01:11  2023-08-07T12:55:23  4           11:36:48
19386930.2    2023-08-07T10:02:35  2023-08-07T12:55:31  4           11:31:44
19386931      2023-08-07T10:01:52  2023-08-07T12:53:06  4           11:24:56
19386931.ba+  2023-08-07T10:01:52  2023-08-07T12:53:07  4           11:25:00
19386931.1    2023-08-07T10:02:51  2023-08-07T12:53:11  4           11:21:20
   
   """
   recnum = 0

   tdays=0
   thh=0
   tmm=0
   tss=0
   
   for record in sys.stdin:
      recnum+=1
      if recnum < 3:
         continue
      fields=re.split("\s+", record.strip())
      cputime=fields[4]
      tokens=re.split("-",cputime)
      days=0
      if len(tokens) == 2:
         days=tokens[0]
         (hh,mm,ss)=re.split(":",tokens[1])
      else:
         (hh,mm,ss)=re.split(":",cputime)

      days=int(days)
      hh=int(hh)
      mm=int(mm)
      ss=int(ss)

      if days > 5:
         print("skipping %s , days > 5"%record)

      else:
         tdays += days
         thh += hh
         tmm += mm
         tss += ss


   print("Totals : (days, hh, mm, ss)")
   print(tdays,thh,tmm,tss)
   print("Total hours 512 CPU")
   HH=tdays*24 + thh + (tmm/60.0) + (tss/(60.0*60.0))
   print(HH)
   print("Theoretical elapsed hours")
   print(HH/512.0)
      

               
def get_options():
   description = """
adds header to a sample sheet if it needs it 
   """
   long_description = """

examples :

cat 2023-08-01.sacct.txt  | ./parse_sacct_cpu.py  --sequencing_platform hiseq -H  /dataset/gseq_processing/active/bin/gbs_prism/etc/sample_sheet_header.csv

cat /dataset/2024_illumina_sequencing_e/scratch/220426_A01439_0069_BHNFW2DRXY/HNFW2DRXY.csv | ./add_sample_sheet_header.py


"""

   parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
   parser.add_argument('--report_type', dest='report_type', type=str, choices = ["CPU"], default = "CPU", help="report type")

   args = vars(parser.parse_args())

   return args
    
def main():
    options = get_options()
    parse(options)
    
        
                                
if __name__ == "__main__":
    main()
