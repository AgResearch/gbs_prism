from __future__ import print_function
#########################################################################
# adapter_collate admin tasks 
#########################################################################
import os
import sys
import csv
import time
import platform
import re
import argparse
import zipfile

# add path to gquery libaries so can use gquery session logging and dbconnection services 
sys.path.append(r'/dataset/gseq_processing/active/bin/gquery/')

from utils import session
from database import dbconnection


DEBUG=False

       
def debug_print(*args):
    if DEBUG:
        print(args)

class adapter_collate_exception(Exception):
    def __init__(self,args=None):
        super(adapter_collate_exception, self).__init__(args)

def get_library_info(s):
    g = dbconnection.g_dbconnection({"interface_type" : "postgres", "host": "postgres_readonly"}, s)

    sql = """
select 
  r.listname as run,
  s.samplename as library,
  g.flowcell,
  g.libraryprepid,
  g.windowsize,
  g.enzyme,
  g.species,
  g.gbs_cohort,
  g.fastq_link,
  r.createddate,
  count(*) 
from 
  ((gbskeyfilefact as g join biosampleob as s on 
  s.obid = g.biosampleob) join biosamplelistmembershiplink as l on 
  l.biosampleob = g.biosampleob) join biosamplelist as r on r.obid = l.biosamplelist
group by 
  r.listname,
  s.samplename,
  g.flowcell,
  g.libraryprepid,
  g.windowsize,
  g.enzyme,
  g.species,
  g.gbs_cohort,
  g.fastq_link,
  r.createddate
order by 
  r.createddate desc
"""

    library_info = g.execute_sql(sql)
    colnames = g.colnames

    return (library_info, colnames)
    
    

def get_fastqc_filename(library_details):
    return

def get_adapter_stats(ziparchive, fastq_datafile, threshholds=[0.05,1.0,2.0,3.0,4.0,5.0,10.0,20.0,30.0,40.0,50.0,60.0,70.0], included = [1]):
    """
    e.g. 
    unzip -c /dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/fastqc/SQ1616_S6_L007_R1_001_fastqc.zip SQ1616_S6_L007_R1_001_fastqc/fastqc_data.txt | more
    """
    z=zipfile.ZipFile(ziparchive)
    zstream = z.open(fastq_datafile)
    adapter_section = False
    colnames = None
    first_positions_breaching_threshholds = len(threshholds) * [None]
    for record in zstream:
        fields=re.split("\t", record.strip())
        if adapter_section:
            if fields[0] == ">>END_MODULE":
                break
            if colnames is None:
                colnames = fields # Position       Illumina Universal Adapter      Illumina Small RNA 3' Adapter   Illumina Small RNA 5' Adapter   Nextera Transposase Sequence    SOLID Small RNA Adapter                
                continue
            else:
                # record is like
                #1       0.0748928001478223      0.0     0.0     0.0     0.0
                # or
                #10-11   0.32983910542668593     0.0     0.0     3.556703779673184E-7    0.0
                # parse the positions and numbers
                fields[0] = re.split("-", fields[0])[0]
                fields = [int(fields[0])] + [ float(field) for field in fields[1:]]

                total_percent = sum( fields[i] for i in included )
                #print(total_percent)
                for i in range(len(threshholds)):
                    if total_percent > threshholds[i] and first_positions_breaching_threshholds[i] is None:
                        first_positions_breaching_threshholds[i] = fields[0]
                        

        else:
            if fields[0] == ">>Adapter Content":
                adapter_section = True

    return (first_positions_breaching_threshholds)
        

def generate_fastqc(s):
    """
    ouput a non-redundant list of fastq links to run through fastqc (i.e. all in the list having different
    real paths )
    """
    (library_info, colnames) = get_library_info(s)

    #print(library_info)

    non_redundant_list = []

    for library_details in library_info:
        d = dict(zip(colnames, library_details))

        if d["fastq_link"] is not None:
            real_fastq_path = os.path.realpath( d["fastq_link"] )
            
            if real_fastq_path not in non_redundant_list:
                non_redundant_list.append( real_fastq_path )
                d["real_path"] = real_fastq_path
                print( d["fastq_link"] )

    print("""launch using : \n

nohup /dataset/gseq_processing/active/bin/gbs_prism/seq_prisms/sequencing_qc_prism.sh -a fastqc -O /dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content `cat /dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/sequence_files.txt` > /dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/fastqc.log 2>&1

""")

def report(s):
    """
    run report 
    """
    (library_info, colnames) = get_library_info(s)

    #print(library_info)

    non_redundant_list = []
    threshholds=[0.05,1.0,2.0,3.0,4.0,5.0,10.0,20.0,30.0,40.0,50.0,60.0,70.0]

    # heading
    print("\t".join( colnames  + ["real_path", "fastqc_results"] + [ "firstreadpos>%4.1f%%adapter"%t for t in threshholds] ))
    for library_details in library_info:
        d = dict(zip(colnames, library_details))

        if d["fastq_link"] is not None:
            real_fastq_path = os.path.realpath( d["fastq_link"] )
            
            if real_fastq_path not in non_redundant_list:
                non_redundant_list.append( real_fastq_path )
                d["real_path"] = real_fastq_path

                fastqc_base = "%s_fastqc"%os.path.splitext(os.path.splitext(os.path.basename(real_fastq_path))[0])[0] # e.g. SQ2970_S41_L008_R1_001.fastq.gz --> SQ2970_S41_L008_R1_001_fastq.zip
                fastqc_zip_archive = "%s.zip"%fastqc_base
                fastqc_adapters_file = "%s/fastqc_data.txt"%fastqc_base
                d["fastqc_results"] = (os.path.join("/dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/fastqc", fastqc_zip_archive), fastqc_adapters_file)
                if os.path.isfile( d["fastqc_results"][0]):
                    first_positions_breaching_threshholds = get_adapter_stats( d["fastqc_results"][0], d["fastqc_results"][1])
                    first_positions_breaching_threshholds = [ {True : 150, False : f}[f is None] for f in first_positions_breaching_threshholds ]

                    print("\t".join( [str(item) for item in library_details]  + [d["real_path"], str(d["fastqc_results"])] + [ "%4.1f"%p for p in first_positions_breaching_threshholds]))
                    
                    
                #    get_adapter_stats("/dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/fastqc/SQ1616_S6_L007_R1_001_fastqc.zip", "SQ1616_S6_L007_R1_001_fastqc/fastqc_data.txt")

                
    

def get_options(): 
    description = """
    """
    long_description = """
examples:

python collate_adapter_content.py -t generate_fastqc > /dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/sequence_files.txt

python collate_adapter_content.py -t report 

    """
    
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('items', type=str, nargs='*',help='space-separated list of items to process (e.g. names of tables etc')
    parser.add_argument('-t', '--task' , dest='task', required=True, type=str,choices=["generate_fastqc","report"])
    
    parser.add_argument('-l','--list_name', dest='list_name', type=str, default=None, help='list name (if requesting list processing)')
    parser.add_argument('-j','--job_name', dest='job_name', type=str, default=None, help='job name (will be used to name output folder if applicable)')        
    parser.add_argument('-r','--root', dest='root', type=str, default="\\\\isamba\\dataset\\gseq_processing\\itmp\\gbs_utils\\collate_adapter_content", help='root folder for ouptut')
    parser.add_argument('-x','--credentials_dict_filename', dest='credentials_dict_filename', type=str, default="\\\\isamba\\dataset\\genophyle_data\\active\\database\\Ndb\\etc\\.credentials_dict", help='credentials dict')
    parser.add_argument('-u','--user', dest='user', type=str, default=os.getenv("USERNAME"), help='user')
    
    args = vars(parser.parse_args())
    args["platform"] = platform.system()

    # adjust paths depending on platform
    if args["platform"] == 'Linux':
        args["user"] = os.getenv("LOGNAME")
        if re.match("^\\\\",args["root"]) is not None:
            args["root"] = os.path.join(*["/"]+[item for item in re.split("\\\\+", args["root"]) if len(item) > 0][1:])
            args["credentials_dict_filename"] = os.path.join(*["/"]+[item for item in re.split("\\\\+", args["credentials_dict_filename"]) if len(item) > 0][1:])


    if args["job_name"] is None:
        if len(args["items"]) == 0:
            args["job_name"] = "adapter_report"
        else:
            args["job_name"] = "%s-job"%os.path.basename(args["items"][0])
             
    return args


def main():   
    options = get_options()

    stats = get_adapter_stats("/dataset/gseq_processing/itmp/gbs_utils/collate_adapter_content/fastqc/SQ1616_S1_L001_R1_001_fastqc.zip", "SQ1616_S1_L001_R1_001_fastqc/fastqc_data.txt")
    print(stats)
    return


    s=session.session(options["root"], options["job_name"], options["credentials_dict_filename"], options["user"], options)
    s.logger.info("using %s"%str(options))

    if options["task"] == "generate_fastqc":
        generate_fastqc(s)
    elif options["task"] == "report":
        report(s)

            
if __name__=='__main__':
    sys.exit(main())    

    

        

