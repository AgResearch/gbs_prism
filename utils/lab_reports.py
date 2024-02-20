#########################################################################
# this script pulls together lab reports related to the hiseq and miseq
# - mostly GBS 
#
# references:
#
#########################################################################
import re
import itertools
import pickle
import os
import sys
import subprocess
import csv
import argparse
#import pyodbc
import hashlib
import time

DEBUG=False

def debug_print(*args):
    if DEBUG:
        print(args)


class lab_report_exception(Exception):
    def __init__(self,args=None):
        super(lab_report_exception, self).__init__(args)

class logger(object):
    """
    work-around for possible issues with standard logging module in combination with
    multiprocessing
    """
    def __init__(self,filename):
        super(logger, self).__init__()
        self.mywriter = open(filename,"a")

    def info(self, msg):
        if self.mywriter is not None:
            self.mywriter.write("%s\t%s\n"%(time.ctime(), msg))
            self.mywriter.flush()
        else:
            raise lab_report_exception("error in logger - writer not initialised !")

    def close(self):
        self.mywriter.close()
        

################################ lab_report base class #####################################
 
class lab_report(object):
    """
    this is the base class for a number of lab report classes    
    """
    def __init__(self,options):
        super(lab_report, self).__init__()

        self.report_name = "lab_report"
        self.options = options 
        self.db_connection = None
        self.credentials_dict_filename = options["credentials_dict_filename"]
        self.lab_report_root = options["lab_report_root"]
        self.action = self.options["action"]
        self.logger = logger(self.get_session_filename("log"))

        self.text_writer = None
        self.csv_writer = None

    def log_print(self,msg):
        self.logger.info(msg)
        print(msg)

    def get_credentials(self):
        """
        get database credentials 
        """
        if not os.path.isfile(self.credentials_dict_filename):
            raise lab_report_exception("error - credentials file %s not found"%self.credentials_dict_filename)
        with open(self.credentials_dict_filename, "r") as creds_dict_file:
            creds_dict=dict( (re.split("\s+", record.strip()) for record in creds_dict_file ) )
            if "%s.%s"%(self.host, self.user)  not in creds_dict:
                raise lab_report_exception("error - no credentials found for %s"%"%s.%s"%(self.host, self.user))
            creds_file=creds_dict["%s.%s"%(self.host, self.user)]
            if not os.path.isfile(creds_file):
                raise lab_report_exception("error - credentials file %s not found"%creds_file)
            with open(creds_file,"r") as creds:
                cread=""
                for record in creds:
                    creds = record.strip()
                    break
                if len(creds) < 5:
                    raise lab_report_exception("error - short creds from %s"%creds_file)
                return creds
                    

    def connect_to_db(self, autocommit=False):
        """
        get a database connection (once only)
        """
        if self.db_connection is None:
            debug_print("DEBUG credentials", self.get_credentials())
            if not autocommit:
                self.db_connection = pyodbc.connect(self.get_credentials())
            else:
                self.db_connection = pyodbc.connect(self.get_credentials(),autocommit=True )
        else:
            debug_print("(re-using existing database connection)")


    def despatch_actions(self):
        """
        abstract in the base class
        """
        return

    def get_report_writer(self):
        """
        set up either tab-delimited or CSV writer
        """
        if self.options["report_output_file"] is not None:
            with open( self.options["report_output_file"],"w") as self.text_writer:
                self.csv_writer = None
                if re.search("\.csv", self.options["report_output_file"], re.I) is not None:
                    self.csv_writer = csv.writer(self.text_writer)

        return
                
        
    def write_report_tuples(self, tuples):
        """
        write report tuple(to either csv or text stream, or stdout / log file )
        """
        if self.text_writer is None and self.csv_writer is None:
            self.log_print("\t".join(tuples))
        elif self.csv_writer is not None:
            self.csv_writer.writerows(tuples)
        else:
            print("\t".join(tuples), file=self.text_writer)
            

    def run_report(self):
        """
        abstract in the base class
        """
        return

    def test_connections(self):
        """
        test the database connedction by running some queries 
        """
        self.connect_to_db()

        cursor = self.db_connection.cursor()
        #cursor.execute("select uidtag from t_animal where animalid = 984")
        #row = cursor.fetchone()
        #return {'uidtag:', row[0]}
    
        #cursor.execute("{call sp_dosomething(123, 'abc')}")

        sql = """
SET NOCOUNT ON;
DECLARE @out_batchnumber int;
EXEC [dbo].[f_getNextInGenericSequence] @next_generic_int = @out_batchnumber OUTPUT;
SELECT @out_batchnumber AS batchnumber;
"""
        params=()
        cursor.execute(sql,params)
        row = cursor.fetchall()
        return{'batchnumber' : row[0][0]}
 
 

    def save(self):
        """
        this saves the session object, to a pickle file. Saved sessions can be resumed and reviewed 
        """
        filename = self.get_session_filename("pickle",1)

        # in case we can't pickle the logger (probably not - e.g. has a file handle) - save it and pickle without it
        current_logger = self.logger
        self.logger = None
        
        pwriter = open(filename, "wb")
        pickle.dump(self, pwriter)
        pwriter.close()

        # restore logger after save
        self.logger = current_logger
        

    def get_logger(self):
        return logger(self.get_session_filename("log"))


    def get_session_filename(self, session_filetype="pickle", arg_iteration = None):
        
        if arg_iteration is None:
            iteration = 1
            while os.path.exists( "%s.%s.%d"%(os.path.join(self.lab_report_root, self.report_name), session_filetype, iteration) ):
                iteration += 1
                if iteration > 100000:
                    raise Exception("unable to get sane file name !")
        else:
            iteration = arg_iteration
            
        return "%s.%s.%d"%(os.path.join(self.lab_report_root, self.report_name), session_filetype, iteration)
            


######################### first base report  ############################
class first_base_report(lab_report):
    """
    first base report (to paste into Green book)
    Reference :
    \\isamba\dataset\gseq_processing\active\bin\gbs_utils\First Base Reports.xlsx

No.	Flowcell	Date	Species	SQ #	Template	Conc	Lane	Side	Cycles	4nM result - Qubit	1st Base Report	Final Density	Difference	% Increase	% PF	% >= Q30	PhiX Spike	Aligned PhiX	Phasing	Pre-phasing	Total Yield	Expected	Yield reached	FastQC checked	Over represented sequences	Mapping	% Good quality	GBSNEG Checked	Neg Count (Tags)	Tags CV	Reads CV	Email sent	Library QC completed and correct	Contact person	# of SNPs	Average Depth	Min co-call rate	Slippery Slope	Comment	
541	CE3EWANXX	4/7/2020	Deer	SQ1257	SQ1257_Deer_PstI	9	1	B	1 x 101	4.3	645.29	1050	404.71	63%	93.38	95.51	2.00%		0.104	0.12	27.22	22.5	Yes				96.34	Yes	25811 12245 44284 10301	10.8	24.5	Y	4/9/2020	Genomnz	65784	2.35	0.019	No	1 poor performer	ZQ7066605    

Hi Alan & Ken

 

I’ve attached the page in the GBS green book that we are currently populated by hand, called the First Base Report.

 

The 1st Base report (highlighted in blue) is taken from the First_Base_Report file that is found in the run folder – and is a html file – which normally looks like this:

 It gives both the top and bottom surface of the Flowcell -but we only take note of the top surface.

 

The area highlighted in green come from information found either on base space, or in the Illumina Sequence Analysis Viewer – the Sequence viewer gets the data somewhere from the run folder – but I haven’t found out where yet.

Everything else comes from the QC.

 
    
    """
    def __init__(self,options):
        super(first_base_report, self).__init__(options)

        self.report_name = "lab_report"
        self.tech = options["tech"] 

        self.source_filepaths = {
            "first_base_report" : None
        }

    def run_report(self):
        self.get_cluster_density(self.options["paths"])


 

    def despatch_actions(self):
        
        if self.action == "get_cluster_density":
            self.get_cluster_density(self.options["paths"])

        return None

    def get_cluster_density(self,sourcefiles):
        """
        this method finds the first base report file  - for example
        /dataset/hiseq/active/200407_D00390_0541_BCE3EWANXX/First_Base_Report.htm
        and scrapes "Cluster Density (k/mm2)" for the top surface
        """
        self.log_print("looking for first base report . . .")
        if self.source_filepaths["first_base_report"] is None:
            for path in self.options["paths"]:
                if os.path.isfile(os.path.join(path, "First_Base_Report.htm")):
                    self.source_filepaths["first_base_report"] = os.path.join(path, "First_Base_Report.htm")
                    break

        if self.source_filepaths["first_base_report"] is None:
            raise lab_report_exception("unable to First_Base_Report.htm using the paths provided")

        self.log_print("found %s"%self.source_filepaths["first_base_report"])
        self.cluster_densities = None
        with open( self.source_filepaths["first_base_report"], "r") as fbr:
            record_field_groups = (re.split("<td>", record.strip()) for record in fbr)
            for group in record_field_groups:
                # ['<tr>', 'Cluster Density (k/mm2)</td>', '645.29</td>', '641.51</td>', '623.25</td>', '650.72</td>', '638.86</td>', '747.56</td>', '689.83</td>', '617.08</td></tr>']
                #print(group)
                if len(group) > 1:
                    if re.match("^Cluster Density", group[1]) is not None:
                        self.cluster_densities = [ re.match("(\d*\.\d*)<", field).groups()[0] for field in group[2:] ]
                        break

        print(self.cluster_densities)
                    

        
                
            

        # we are scraping:
#<html>
#<head>
#<!--RUN_TIME Tuesday, 07 April, 2020 10:41:23-->
#</head>
#<body>
#<title>First Base Report</title>
#<h2>First Base Report</h2>
#<h3>200407_D00390_0541_BCE3EWANXX</h3>
#<br>
#<h3>Top Surface<br><br></h3>
#<table border="1" cellpadding="5">
#<tr><td>Metric</td><td>Lane 1</td><td>Lane 2</td><td>Lane 3</td><td>Lane 4</td><td>Lane 5</td><td>Lane 6</td><td>Lane 7</td><td>Lane 8</td></tr>
#<tr><td>Cluster Density (k/mm2)</td><td>645.29</td><td>641.51</td><td>623.25</td><td>650.72</td><td>638.86</td><td>747.56</td><td>689.83</td><td>617.08</td></tr>
#<tr><td>A Intensity</td><td>34580.17</td><td>34297.83</td><td>33617.5</td><td>33002.5</td><td>33968.67</td><td>34092.83</td><td>33212.67</td><td>35114.33</td></tr>
#<tr><td>C Intensity</td><td>52488.83</td><td>51755.5</td><td>51243</td><td>50176.67</td><td>51599.5</td><td>51548.33</td><td>50537.17</td><td>53282.5</td></tr>
#<tr><td>G Intensity</td><td>55034.83</td><td>53799</td><td>51779.17</td><td>50546.5</td><td>51406.83</td><td>52327.67</td><td>50517.33</td><td>51998</td></tr>
#<tr><td>T Intensity</td><td>92491.34</td><td>91493.34</td><td>89254.66</td><td>87302.66</td><td>88788.66</td><td>88953.16</td><td>85963.84</td><td>90863.5</td></tr>
#<tr><td>A Focus Score</td><td>86.89</td><td>86.92</td><td>86.46</td><td>87.17</td><td>87.09</td><td>89.97</td><td>88.62</td><td>87.13</td></tr>
#<tr><td>C Focus Score</td><td>84.54</td><td>84.67</td><td>84.11</td><td>84.91</td><td>84.79</td><td>87.57</td><td>86.34</td><td>84.88</td></tr>
#<tr><td>G Focus Score</td><td>88.42</td><td>88.32</td><td>87.85</td><td>88.59</td><td>88.46</td><td>91.32</td><td>89.95</td><td>88.55</td></tr>
#<tr><td>T Focus Score</td><td>86.74</td><td>86.7</td><td>86.31</td><td>86.99</td><td>86.85</td><td>89.48</td><td>88.24</td><td>86.97</td></tr>
#</table>
        
        
        
                    

def despatch_actions(options):
    print("processing %s "%options["action"])

    results=[]

    if options["report_type"] == "first_base_report":
        report_class = first_base_report
    else:
        raise lab_report_exception("unsupported report type : %s"%options["report_type"])

    report_session = report_class(options)
    report_session.despatch_actions()


def run_report(options):
    print("running report using %s "%options["action"])

    if options["report_type"] == "first_base_report":
        report_class = first_base_report
    else:
        raise lab_report_exception("unsupported report type : %s"%options["report_type"])

    report_session = report_class(options)
    report_session.run_report()    
    

def test_connections(options):
    print("testing connections")

    report_session = lab_report("test", options)
    return report_session.test_connections()
 

def get_options():
    description = """
    """
    long_description = """

examples :

python lab_reports.py -t first_base_report -a get_cluster_density /dataset/hiseq/active/200407_D00390_0541_BCE3EWANXX
python lab_reports.py -t first_base_report /dataset/hiseq/active/200407_D00390_0541_BCE3EWANXX

    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', type=str, nargs='*',help='space-seperated list of files or folders to process or consider (if any)')
    parser.add_argument('-t', '--report_type' , dest='report_type', required=True, type=str,  choices=["test_connections","first_base_report"], help="report type")
    parser.add_argument('-T', '--tech' , dest='tech', type=str, default = 'hiseq',  choices=["hiseq","miseq"], help="technology in use - e.g. miseq or hiseq")
    parser.add_argument('-a', '--action', dest='action', default=None, type=str,
                         help="not usually used - but can be used to do one step at a time (e.g. test/debug. Examples: ") 
    parser.add_argument('-r','--lab_report_root', dest='lab_report_root', type=str, default="/dataset/gseq_processing/itmp/lab_reports", help = "path for log files etc")    
    parser.add_argument('-n','--dry_run', dest='dry_run', action='store_const', default = False, const=True, help='dry run only')
    parser.add_argument('-x','--credentials_dict_filename', dest='credentials_dict_filename', type=str, default="\\\\isamba\\dataset\\genophyle_data\\active\\database\\Ndb\\etc\\.credentials_dict", help='credentials dict')
    parser.add_argument('-O','--report_output_file', dest='report_output_file', type=str, default=None, help='report output file')
    

    args = vars(parser.parse_args())
        
    return args


def main():
    options = get_options()
    print("using %s"%str(options))

    if options["report_type"] == "test_connections":
        results = test_connections(options)
        print(results)
    else:
        if options['action'] is not None:
            results=despatch_actions(options)
        else:
            results = run_report(options)
        if results is not None:
            print(results)
        
            

if __name__=='__main__':
    sys.exit(main())    

    

        

