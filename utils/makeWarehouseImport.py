#!/usr/bin/python

from types import *
import os
import sys
import re
import csv
 
def main():
    """
    this script reads an input file (either CSV or tab delimited) and parses the heading and data to 
    generate a typed table create statement with sensible column names
    """
 
    # parse o.l. args
    if len(sys.argv) < 2:
        raise Exception("usage : python makeWarehousImport.py myfile [format=csv|tab] [null=char] [skipshort=N] [rewrite=tab|CSV] [headerlinenumber=N] [precisgroupsize=5]")

    argDict = dict([ re.split('=',arg) for arg in sys.argv if re.search('=',arg) != None ])
    print "using %s"%str(argDict)

 
 
    format="tab"
    null=""
    skipshort = None
    rewrite = None
    headerlinenumber = 1
    precisgroupsize = None

    if "format" in argDict:
        format = argDict["format"]

    if "null" in argDict:
        null = argDict["null"]

    if "skipshort" in argDict:
        try:
           skipshort = int(argDict["skipshort"])
        except:
           raise Exception("failed parsing the short line skip amount")

    if "rewrite" in argDict:
        rewrite = argDict["rewrite"]

    if "precisgroupsize" in argDict:
        precisgroupsize = int(argDict["precisgroupsize"])

    if "headerlinenumber" in argDict:
        headerlinenumber = int(argDict["headerlinenumber"])

    if not os.path.exists(sys.argv[1]):
        raise Exception("file %s does not exist"%sys.argv[1])
 
    # set up tab delimited or CSV reader
    reader = file(sys.argv[1])
    if format.lower() == "csv":
        reader = csv.reader(file(sys.argv[1]))
 
 
    rowcount = 0
    fieldNames = []
    fieldTypes = []
    fieldWidths = []
    # process the file

    rewriter = None;
    if rewrite != None:
        if rewrite == "csv":
            rewriter = csv.writer(file("%s.%s"%(sys.argv[1],"rewritten"),"w"))
        elif rewrite == "tab":
            rewriter = file("%s.%s"%(sys.argv[1],"rewritten"),"w")
        else:
            raise Exception("unsupported format for rewriter %s"%rewrite)

    groups = {}

    for row in reader:
        rowcount += 1

        if rowcount < headerlinenumber:
            continue

        rowTuple = row
        #print "processing %s"%str(rowTuple)
        if format == "tab":
            rowTuple = re.split("\t",row)

        rowTuple = [{True : "", False : item}[item == None] for item in rowTuple]
        rowTuple = [item.strip() for item in rowTuple]
        rowTuple = [{True : None, False : item}[item == ""] for item in rowTuple]

        if null != "":
            rowTuple = [re.sub("^%s$"%null, "", item) for item in rowTuple]

        rowTuple = [{True : None, False : item}[item == ""] for item in rowTuple]

        if skipshort != None:
            if len(rowTuple) < skipshort:
                continue

        if precisgroupsize != None:
            #print rowTuple
            #print groups
            if rowTuple[0] not in groups:
                groups[rowTuple[0]] = 1
            else:
                groups[rowTuple[0]] += 1

            if groups[rowTuple[0]] > precisgroupsize:
                continue
              
           
 
        #print "processing split %s"%str(rowTuple)
        if rowTuple != None:
            if isinstance(rowTuple,ListType):
                if len(rowTuple) > 0:
                    if len(fieldNames) == 0:
                        # process the header
                        fieldTypes = len(rowTuple) * [IntType]
                        fieldWidths = len(rowTuple) * [0]
                        # obtain db-friendly column names from the column headings
                        for fieldName in rowTuple:
                            if fieldName == None:
                                fieldName = "null"
                            fieldName = fieldName.strip()
                            fieldName = re.sub("^[\-]","minus",fieldName)
                            fieldName = re.sub("[\[\]\(\)]","",fieldName)
                            fieldName = re.sub("[\-\*\.]","_",fieldName)
                            fieldName = re.sub("\s+_\s+","_",fieldName)
                            fieldName = re.sub("\s+","_",fieldName)
                            fieldName = re.sub("[\%]","pct",fieldName)
                            fieldName = re.sub("[\/]","over",fieldName)
                            fieldName = re.sub("^\#","",fieldName)
                            fieldName = re.sub("\#$","",fieldName)
                            fieldName = re.sub("\#","_",fieldName)
                            fieldName = re.sub("\,","_",fieldName)
                            fieldName = re.sub("\:","_",fieldName)
                            fieldName = re.sub("\"","",fieldName)
                            fieldName = re.sub("\'","prime",fieldName)
                            fieldName = re.sub("\+","plus",fieldName)

 
                            if len(fieldName) == 0:
                                fieldName = "col"
 
                            # prefix numeric names with an N
                            if re.search("^[1234567890]",fieldName) != None:
                                fieldName = 'n' + fieldName
 
                            fieldName = re.sub("^max$","maximum",fieldName)
                            fieldName = re.sub("^min$","minimum",fieldName)
 
                            if fieldName in fieldNames:
                                count = 1
                                while "%s_%s"%(fieldName,count) in fieldNames:
                                    count += 1
 
                                fieldName = "%s_%s"%(fieldName,count)
 
                            fieldNames.append(fieldName)
                    else:
                        # process the data
                        # check for field types - we test if we can parse numbers, and if the numbers are integers.
                        # once something is demoted from int to float it cannot become int again. Once something is
                        # demoted from float to string it cannot become numeric again
                        if len(rowTuple) != len(fieldNames):
                            print "Warning : data row length (%s) mismatch with header row length (%s) at row %s"%(len(rowTuple), len(fieldNames), rowcount)
                            continue
                        for i in range(0,len(rowTuple)):
                            if rowTuple[i] != None:
                                if fieldTypes[i] != StringType:  
                                    try:
                                        junk = float(rowTuple[i])
                                        if fieldTypes[i] == IntType:
                                            if junk - int(junk) != 0 or re.search("\.",rowTuple[i]) != None:
                                                fieldTypes[i] = FloatType
                         
                                    except:
                                        fieldTypes[i] = StringType
 
                                if fieldTypes[i] == StringType:
                                    if rowTuple[i] != None:
                                        fieldWidths[i] = max(len(rowTuple[i]), fieldWidths[i])

        if rewrite != None:
            rowTuple = [{True : "", False : item}[item == None] for item in rowTuple]
            if rewrite == "csv":
                rewriter.writerow(rowTuple)
            elif rewrite == "tab":
                rewriter.write(reduce(lambda x,y:"%s\t%s"%(x,y),rowTuple))
                rewriter.write("\n")
 

 
    # round field Widths up to nearest 10
    fieldWidths = [int( 1.0 + item / 10.0) * 10 for item in fieldWidths]
 
    # print summary of what we found                             
    print "Names : %s"%str(fieldNames)
    print "Types : %s"%str(fieldTypes)
    print "Widths : %s"%str(fieldWidths)
 
    # set up and prnit the table create statement
    sql = """
    create table ("""
 
    sep=""
    for i in range(0, len(fieldNames)):
        sql +=  """%s 
           %s %s"""%(sep,fieldNames[i],{IntType:"int", FloatType:"float", StringType:"varchar(%s)"%fieldWidths[i]}[fieldTypes[i]])
        sep=","
    sql +=  ") without oids;"
 
    print "\n\n\n%s"%sql

    if rewriter != None:
        rewriter.close()
 
 
 
if __name__ == "__main__" :
    main()
