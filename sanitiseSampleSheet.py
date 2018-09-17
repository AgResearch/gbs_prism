#!/bin/env python

import csv 
import sys
import re
import string
import argparse

def get_import_value(value_dict, regexp):
   matching_keys = [re.search(regexp, key, re.IGNORECASE).groups()[0] for key in value_dict.keys() if re.search(regexp, key, re.IGNORECASE) is not None]
   #print value_dict
   #print regexp
   #print matching_keys
   if len(matching_keys) == 0:
      value = ""
   elif len(matching_keys) == 1:
      value = value_dict[matching_keys[0]]
   elif reduce(lambda x,y:x+y, [ len(value_dict[key].strip()) for key in matching_keys ]) == 0:
      value = ""
   else:
      value = "; ".join("%s=%s"%(key, value_dict[key]) for key in matching_keys)   
   return value
   
   

def sanitise(options):

   rowcount = 1
   numcol = None
   DEBUG=False

   csvreader = csv.reader(sys.stdin)
   csvwriter = csv.writer(sys.stdout)
   filter_record = True
   standard_header = ["fcid","lane","sampleid","sampleref","sampleindex","description","control","recipe","operator","sampleproject","sampleplate","samplewell","downstream_processing","basespace_project"]

   for record in csvreader:
      
      if filter_record:
         # see if we have hit header
         #print record
         header_matches = [True for item in record if re.match("(lane|sample[_]*id|sample[_]*project)",item,re.IGNORECASE) is not None]
         #print header_matches
         if len(header_matches) == 3:
            filter_record = False
            header = record

            # output header
            csvwriter.writerow(standard_header)
      else:
         # skip any embedded section headings
         if re.search("\[.*\]",record[0]) is not None:
            continue
         # prepare ther record, including the following mappings:
         #Lane->lane
         #Sample_ID->sampleid
         #Sample_Name->sampleref
         #Sample_Plate->sampleplate *
         #Sample_Well -> samplewell *
         #*Index* -> sampleindex (concatenate)
         #Sample_Project -> sampleproject
         #Description -> description
         record_dict = dict(zip(header, record))
         out_record_dict  = {}
         out_record_dict["fcid"] = options["fcid"]
         out_record_dict["lane"] = get_import_value(record_dict, "(lane)")
         out_record_dict["sampleid"] = get_import_value(record_dict, "(sample[_]*id)")
         out_record_dict["sampleref"] = get_import_value(record_dict, "(sampleref|sample[_]*name)")
         out_record_dict["sampleindex"] = get_import_value(record_dict, "(.*index.*)")
         out_record_dict["description"] = get_import_value(record_dict, "(description)")
         out_record_dict["control"] = get_import_value(record_dict, "(control)")
         out_record_dict["recipe"] = get_import_value(record_dict, "(recipe)")
         out_record_dict["operator"] = get_import_value(record_dict, "(operator)")
         out_record_dict["sampleproject"] = get_import_value(record_dict, "(sample[_]*project)")
         out_record_dict["sampleplate"] = get_import_value(record_dict, "(sample[_]*plate)")
         out_record_dict["samplewell"] = get_import_value(record_dict, "(sample[_]*well)")
         out_record_dict["downstream_processing"] = get_import_value(record_dict, "(downstream_processing)")
         out_record_dict["basespace_project"] = get_import_value(record_dict, "(basespace_project)")
         
                                    
         record = [out_record_dict.get(key,"") for key in standard_header]
         
         csvwriter.writerow(record)


def get_options():
   description = """
prepares a sanitised version of a sample sheet for subseqent import into the database sample sheet table.
   """
   long_description = """

example : cat myfile.csv | sanitiseSampleSheet.py -r 161205_D00390_0274_AC9KW9ANXX


"""

   parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
   parser.add_argument('-r', dest='run', required=True , help="name of run")

   args = vars(parser.parse_args())

   # parse fcid
   mymatch=re.match("^\d+_\S+_\d+_.(\S+)", args["run"])
   if mymatch is None:
      raise Exception("unable to parse fcid from run")

   args["fcid"] = mymatch.groups()[0]
       
   return args

        
    
def main():
    options = get_options()
    sanitise(options)
    
        
                                
if __name__ == "__main__":
    main()
