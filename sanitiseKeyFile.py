#!/bin/env python

# some keyfiles are padded with extra empty columns at the right hand end , this upsets the database importer
# to use; some have empty rows at the end - ditto. To use , e.g. 
# cp /dataset/hiseq/active/key-files/SQ2530.txt /dataset/hiseq/active/key-files/SQ2530.txt.bu2
# cat /dataset/hiseq/active/key-files/SQ2530.txt.bu2 | ./sanitiseKeyFile.py > /dataset/hiseq/active/key-files/SQ2530.txt
# cat /dataset/hiseq/active/key-files/SQ2530.txt | ./sanitiseKeyFile.py > junk
#
# 11/2017
# added reordering columns as well , to the order expeted by the importer

import sys
import re
import string

# canonical fields and ordering is :
#Flowcell,Lane,Barcode,Sample,PlateName,PlateRow,PlateColumn,LibraryPrepID,counter,Comment,Enzyme,Species,NumberOfBarcodes,bifo,control,windowsize,gbscohort,fastq

# the following are optional
#counter,bifo,control,windowsize,gbscohort,fastq

# set up array of field descriptors in correct order. An array of tuples which contain
# (regexp to (uniquely) find field , optional True or False)
global field_descriptors
field_descriptors = [("(flow|fcid)",False),("lane",False),("^barcode",False),("sample", False),("platename", False),\
                     ("row",False),("column",False),("prep",False),("counter",True),("comment",False),("enzyme",False),\
                     ("species",False),("number\s*of\s*bar",False),("bifo",True),("control",True),("window\s*size",True),\
                     ("cohort",True),("fastq",True)]


def get_field_index(header_record):

   # get an index of where each canonical field is in the header
   field_index = len(field_descriptors) * [None]
   tokens=re.split("\t",header_record.strip())

   for i in range(0, len(tokens)):
      token = tokens[i]
      for j in range(0, len(field_descriptors)):
         (regexp,optional) = field_descriptors[j]
         if re.search(regexp, token, re.IGNORECASE) is not None:
            if field_index[j] is not None:
               print "*** sanitiseKeyFile.py : matched %s more than once in %s ***"%(regexp, header_record)
               sys.exit(1)
            else:
               field_index[j] = i

   for j in range(0, len(field_descriptors)):
      (regexp,optional) = field_descriptors[j]
      if field_index[j] is None and not optional:
         print "%s is missing and not optional"%regexp
         sys.exit(1)

   return field_index
      
   
def get_canonicalised_token_array(field_index, num_fields, record):
   tokens = re.split("\t", record.strip())
   if len(tokens) < num_fields:
      # allow limited padding
      if num_fields - len(tokens) in (1,2,3):
         tokens = tokens + ([""] * ( num_fields - len(tokens) ))
      else:
         print "error short record %s - has %d fields expecting %d (i.e. %s)"%(record, len(tokens), num_fields, field_index)
         sys.exit(1)

   token_array = [ tokens[field_index[j]].strip() for j in range(0,len(field_index)) if field_index[j] is not None ]
   return token_array

def deprecated_get_padded_token_array(numcol, record):
   padded_token_array = []
   record_numcol = len(re.split("\t", record.strip()))
   if DEBUG:
      print "****", record_numcol,numcol,re.split("\t", record.strip())
   if len(record.strip()) == 0:
      pass
   if numcol - record_numcol in (1,2,3):   # allow limited padding
      # pad with one or more empty strings - sometimes the fastq column is missing and sometimes also the bifo column
      padded_token_array = re.split("\t", record.strip())[0:numcol] + [""]*(numcol-record_numcol)
      #print string.join(re.split("\t", record.strip())[0:numcol] + [""]*(numcol-record_numcol), "\t")
      if DEBUG:
         print "---->", len(re.split("\t", string.join(re.split("\t", record.strip())[0:numcol] + [" "], "\t"))),re.split("\t", string.join(re.split("\t", record.strip())[0:numcol] + [" "], "\t"))
   elif numcol - record_numcol == 0:
      padded_token_array=re.split("\t", record.strip())[0:numcol]
      #print string.join(re.split("\t", record.strip())[0:numcol], "\t")
   elif numcol != record_numcol:
      raise Exception("error reading keyfile at record %d - expected %d columns but see %d"%(rowcount, numcol, record_numcol))
   else:
      raise Exception("error reading keyfile at record %d - fell through the logic"%rowcount)

   return padded_token_array

rowcount = 1
numcol = None
DEBUG=False
record_length_first_encountered = None
for record in sys.stdin:
   if rowcount == 1 :
      header_token_array = re.split("\t", record.strip())
      numcol = len(header_token_array)
      field_index = get_field_index(record)
   else:
      if len(record.strip()) == 0:
         continue
      #padded_token_array=get_padded_token_array(numcol, record)
      padded_token_array=get_canonicalised_token_array(field_index, len([item for item in field_index if item is not None]), record)
      if len(padded_token_array) > 0:
         print string.join(padded_token_array, "\t")
   rowcount += 1


