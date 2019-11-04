#!/bin/env python

import csv 
import sys
import re
import string
import argparse
import datetime 
import itertools
import os

def add_header(options):
   """
   output sample sheet with header added if necessary, padding header if necessary to match
   number of columns in sample sheet
   """
  
   csvwriter = csv.writer(sys.stdout)

   # get data
   with open(options["header_file"],"r") as header:
      header_records = [ record for record in csv.reader(header) ]
   for record in header_records:
      if record[0] == 'Date':
         record[1] = record[1]%{"today" : datetime.date.today().strftime("%d/%m/%Y")}
   sample_sheet_records = [ record for record in csv.reader(sys.stdin)]

   # calculate passding
   header_numcol = len(header_records[0])
   sample_sheet_numcol = max( (len(record) for record in sample_sheet_records ))

   # test if header already present 
   header_present = reduce(lambda x,y: x or y, [ record[0] == '[Header]' for record in sample_sheet_records ] , False)
   adapter_config_present = reduce(lambda x,y: x or y, [ record[0] == 'Adapter' for record in sample_sheet_records ] , False)

   if header_present and not adapter_config_present:
      raise Exception(" error , header in the sample sheet supplied does not specify adapter")

   # output sample sheet, adding and padding header if necessary
   if not header_present:
      for record in header_records + sample_sheet_records:
         csvwriter.writerow(record +  (sample_sheet_numcol - len(record)) * [""])
   else:
      for record in sample_sheet_records:
         csvwriter.writerow(record)
         
   
def get_options():
   description = """
adds header to a sample sheet if it needs it 
   """
   long_description = """

example : cat /dataset/hiseq/active/191021_D00390_0510_BCE3UBANXX/SampleSheet.csv | ./add_sample_sheet_header.py -H  /dataset/gseq_processing/active/bin/gbs_prism/etc/sample_sheet_header.csv 


"""

   parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
   parser.add_argument('-H', dest='header_file', required=True , help="header to add")


   args = vars(parser.parse_args())

   if not os.path.isfile(args["header_file"]):
      raise Exception("header file %s does not exist"%args["header_file"])

   return args
    
def main():
    options = get_options()
    add_header(options)
    
        
                                
if __name__ == "__main__":
    main()
