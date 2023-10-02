#!/usr/bin/env python
#
# make an HTML page to view the output of SelfRelDepth.r together with the orginal plot
# - the output should be sent to /bifo/scratch/2023_illumina_sequencing_c/postprocessing/ so that the paths
# work when opened 
#
import sys
import os
import re
import itertools
import string
import exceptions
import argparse


header="""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
   "httpd://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title>
Summary of GHWdgm.05diagdepth.png
</title>
</head>
<body>
<h1> Summary of GHWdgm.05diagdepth.png (sorted by pval ascending)</h1>
<h2> (to query, sort etc - right click and export to Excel ) </h2>
<table id=plots width=90%% align=center>
<tr>
<td>
<b> species </b>
</td>
<td>
<b> library </b>
</td>
<td>
<b>GBS cohort</b>
</td>
<td>
<b>Enzyme</b>
</td>
<td>
<b>Sample Count</b>
</td>
<td>
<b> Slope </b>
</td>
<td>
<b> pval </b>
</td>
<td>
<b> plot </b>
</td>
<td>
<b> path </b>
</td>
</tr>
<tr>
"""

record_block="""
<tr>
<td>
%(species)s
</td>
<td>
%(library)s
</td>
<td>
%(gbs_cohort)s
</td>
<td>
%(enzyme)s
</td>
<td>
%(count)s
</td>
<td>
%(slope)s
</td>
<td>
%(pval)s
</td>
<td>
<img src=%(image_path)s height="300" width="300"/>
</td>
<td>
<font size="-1">
%(path)s
</font>
</td>
</tr>
"""

footer="""
</table>
</body>
</html>
"""

def generate_run_plot():
    print header

    record_array  = [ re.split("\t", record.strip() ) for record in sys.stdin if len(record.strip()) > 1 ]
    record_array = sorted(record_array, cmp=lambda r1,r2: cmp(float(r1[2]), float(r2[2])))
    
    for record in record_array:
        # these are like
        # /bifo/scratch/2023_illumina_sequencing_c/postprocessing/180130_D00390_0343_BCBG7MANXX.gbs/SQ0618.processed_sample/uneak/PstI.PstI.cohort/KGD -0.06391309 2.17314e-15
        #/dataset/gseq_processing/scratch/gbs/140624_D00390_0044_BH9PEBADXX/SQ0001.all.PstI.PstI/KGD     -0.05257605     0.1317527       cattle  PstI    PstI    13
        #/dataset/gseq_processing/scratch/gbs/140624_D00390_0044_BH9PEBADXX/SQ0001.all.PstI.PstI/KGD.orig        -0.05257605     0.1317527       cattle  PstI    PstI    13

        #print record
        #['/bifo/scratch/2023_illumina_sequencing_c/postprocessing/180627_D00390_0375_BCCHBJANXX.gbs/SQ2741.processed_sample/uneak/all.ApeKI.ApeKI.cohort/KGD',
        # '-0.5114565', '1.276835e-12', 'white', 'clover', 'ApeKI', 'ApeKI', '96']
        #print "DEBUG processing %s"%record

        (path, slope,pval,species, gbs_cohort, enzyme, count) = record
        # need to fix up path - from this
        # /bifo/scratch/2023_illumina_sequencing_c/postprocessing/180130_D00390_0343_BCBG7MANXX.gbs/SQ0618.processed_sample/uneak/PstI.PstI.cohort/KGD
        # to this
        # 180816_D00390_0393_ACCRBRANXX.gbs/SQ0782.processed_sample/uneak/all.GOAT.PstI.cohort/KGD/GHWdgm.05diagdepth.png
        #
        # this /dataset/gseq_processing/scratch/gbs/180925_D00390_0404_BCCVH0ANXX/SQ0797.all.PstI-MspI.PstI-MspI/KGD
        # to this
        # /dataset/gseq_processing/scratch/gbs/180925_D00390_0404_BCCVH0ANXX/SQ0797.all.PstI-MspI.PstI-MspI/KGD/GHWdgm.05diagdepth.png
        #
        if re.search("gseq_processing", path) is not None:
            relpath=os.path.relpath(path, "/dataset/gseq_processing/scratch/gbs")
            image_path=os.path.join(relpath, "GHWdgm.05diagdepth.png")
        else:
            relpath=os.path.relpath(path, "/dataset/2023_illumina_sequencing_c/scratch/postprocessing")
            image_path=os.path.join("old_plots", relpath,"GHWdgm.05diagdepth.png")


        # get library name - temp hack
        library=re.split("\.",re.split("/", relpath)[1])[0]
        
        run_match=re.search("/dataset/gseq_processing/scratch/gbs/([^\/]+)/",path)
        if run_match is None:
            run_match=re.search("/dataset/2023_illumina_sequencing_c/scratch/postprocessing/([^\/]+)\.gbs/",path)
            if run_match is None:
                print "Error could not parse run from %s"%path
                continue

        run=run_match.groups()[0]

        if os.path.exists(os.path.join("/dataset/2023_illumina_sequencing_c/scratch/postprocessing/", "%s_plots.html"%run)):
            plots_page="\\\\isamba\\dataset\\2023_illumina_sequencing_c\\scratch\\postprocessing\\%s_plots.html"%run
            path="<a href=\"%s\" target=plots_page>%s</a>"%(plots_page, os.path.join("/dataset/2023_illumina_sequencing_c/scratch/postprocessing/", "%s_plots.html"%run))
        else:
            plots_page="file:///\\\\isamba\\" + path[1:].replace("/","\\")
            path="<a href=\"%s\" target=plots_page>%s</a>"%(plots_page, path)


        print record_block%{"slope":slope, "pval":pval, "image_path" : image_path, "path" : path,\
                            "species":species, "library":library, "gbs_cohort":gbs_cohort, "enzyme":enzyme, "count":count}

                        
    print footer
        
def main():

    generate_run_plot()


if __name__ == "__main__":
   main()



        

