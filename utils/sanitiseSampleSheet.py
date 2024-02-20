#!/bin/env python

import csv 
import sys
import re
import string
import argparse
import datetime 

header1="""[Header],,,,,,,,,,,,,
IEMFileVersion,4,,,,,,,,,,,,
Date,%(today)s,,,,,,,,,,,,
Workflow,GenerateFASTQ,,,,,,,,,,,,
Application,HiSeq FASTQ Only,,,,,,,,,,,,
Assay,TruSeq HT,,,,,,,,,,,,
Description,,,,,,,,,,,,,
Chemistry,Amplicon,,,,,,,,,,,,
,,,,,,,,,,,,,
[Reads],,,,,,,,,,,,,
101,,,,,,,,,,,,,
,,,,,,,,,,,,,
[Settings],,,,,,,,,,,,,
ReverseComplement,0,,,,,,,,,,,,
Adapter,AGATCGGAAGAGCACACGTCTGAACTCCAGTCA,,,,,,,,,,,,
AdapterRead2,AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT,,,,,,,,,,,,
[Data],,,,,,,,,,,,,"""


def get_import_value(value_dict, regexp):
   #print "DEBUG get_import_value: value_dict=%s"%str(value_dict)
   #print "DEBUG get_import_value: regexp=%s"%str(regexp)
   #matching_keys = [re.search(regexp, key, re.IGNORECASE).groups()[0] for key in value_dict.keys() if re.search(regexp, key, re.IGNORECASE) is not None]
   matching_keys = [key for key in value_dict.keys() if re.search(regexp, key, re.IGNORECASE) is not None]
   
   #print value_dict
   #print regexp
   #print "DEBUG get_import_value: matching_keys=%s"%str(matching_keys)
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
   column_heading_sets = {
      "sample" : ["fcid","lane","sampleid","sampleref"],
      "indices" : ["sampleindex"],
      "other" : ["description","control","recipe","operator","sampleproject","sampleplate","samplewell","downstream_processing","basespace_project"],
      "coerced_for_database" : ["fcid","lane","sampleid","sampleref","sampleindex","description","control","recipe","operator","sampleproject","sampleplate","samplewell","downstream_processing","basespace_project"]
   }
  
   if options["add_header"]:
      print header1%{"today" : datetime.date.today().strftime("%d/%m/%Y")}
      
   for record in csvreader:
      
      if filter_record:
         # see if we have hit header
         #print record
         header_matches = [True for item in record if re.match("(lane|sample[_]*id|sample[_]*project)",item,re.IGNORECASE) is not None]
         #print header_matches
         if len(header_matches) == 3:
            filter_record = False
            header = record

            # discover the index columns
            index_column_names = [item  for item in record if re.search("index",item,re.IGNORECASE) is not None]
            if len(index_column_names) > 0:
               column_heading_sets["indices"] = index_column_names

            #print "DEBUG index column names : %s"%str(column_heading_sets["indices"])
               

            # output header
            if options["target"] == "bcl2fastq":
               column_headings = column_heading_sets["sample"] + column_heading_sets["indices"] + column_heading_sets["other"]
            elif options["target"] == "database":
               column_headings = column_heading_sets["coerced_for_database"] 
            else:
               raise Exception("unknown target %s"%target)
               
            csvwriter.writerow(column_headings)
      else:
         # skip any embedded section headings
         if re.search("\[.*\]",record[0]) is not None:
            continue
         if re.search("^#",record[0]) is not None:
            csvwriter.writerow([record[0]] + (len(column_headings)-1) * [''])
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
         #print "DEBUG : record_dict = %s"%str(record_dict)
         out_record_dict  = {}
         out_record_dict["fcid"] = options["fcid"]
         out_record_dict["lane"] = get_import_value(record_dict, "(lane)")
         out_record_dict["sampleid"] = get_import_value(record_dict, "(sample[_]*id)")
         out_record_dict["sampleref"] = get_import_value(record_dict, "(sampleref|sample[_]*name)")

         if options["target"] == "bcl2fastq":
            for column_heading in column_heading_sets["indices"]:
               out_record_dict[column_heading] = get_import_value(record_dict, "(^%s$)"%column_heading)

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
         if out_record_dict["downstream_processing"] == "" and options["supply_missing"]:
            if get_import_value(record_dict, "(.*index.*)")  == "":
               out_record_dict["downstream_processing"] = "GBS"
               out_record_dict["basespace_project"] = out_record_dict["sampleproject"]
               out_record_dict["sampleproject"] = out_record_dict["sampleid"]
            else:
               out_record_dict["downstream_processing"] = "GTSEQ"
               out_record_dict["basespace_project"] = out_record_dict["description"]
                                                  
         record = [out_record_dict.get(key,"") for key in column_headings]
         
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
   parser.add_argument('--supply_missing' , dest='supply_missing', default=False,action='store_true', help="add missing sections and headers")
   parser.add_argument('--add_header' , dest='add_header', default=False,action='store_true', help="add sample sheet header")
   parser.add_argument('--target' , dest='target', default="bcl2fastq" , type=str, choices=["database","bcl2fastq"] , help="controls format of filtered sample sheet - if bcl2fastq, minimal changes ; if database , coerce for database import")


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
