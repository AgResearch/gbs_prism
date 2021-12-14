#!/usr/bin/env python


#
# this script creates an html document for each cohort of
# a gbs run, which presents the various plots generated , and
# has links to text output
#
import os
import re
import itertools
import string
import exceptions
import argparse


header1="""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
   "httpd://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title>
Overview of %(run_folder)s
</title>
</head>
<body>
<h1> Q/C Summaries for <a href="http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=%(run_folder)s&context=default">%(run_folder)s</a> </h1>
<ul>
<li>  <a href="#overview_plots"> Overview Summaries (before demultiplexing) </a> 
    <ul>
        <li> <a href="#samplesheet"> Sample Sheet </a>
        <li> <a href="#bclconvert"> bclconvert reports (clustering etc)</a>
        <li> <a href="#tags_reads"> Tags, Reads Mean,Standard Deviation,CV  </a>
        <li> <a href="#barcode_yield"> Barcode yields </a>        
        <li> <a href="#bwa"> BWA Alignment Rates </a>
        <li> <a href="#multiqc"> MULTIQC (mashup of FASTQC across lanes)</a>        
        <li> <a href="#fastqc"> FASTQC output</a>
        <li> <a href="#raw_kmer"> Raw kmer distributions </a>
        <li> <a href="#trimmed_kmer"> Trimmed kmer distributions </a>
    </ul>
<li>  <a href="#other_overview_plots"> Other Overview Summaries </a>
    <ul>
        <li> <a href="#slippery_slope"> Cumulative self-relatedness ~ depth </a>
    </ul>
<li> <a href="#sample_plots"> Sample Level Summaries (after demultiplexing)</a> 
    <ul>
        <li> <a href="#cohort_plots"> Cohort Plots </a>
        <li> <a href="#Preview common sequence (trimmed fastq)"> Common sequence (trimmed) </a>
        <li> <a href="#Preview common sequence (low depth tags)"> Common sequence (LD tags) </a>
    </ul>
</ul>
</p>
<h2 id=overview_plots> Overview Summaries </h2>

"""
overview_section="""
<p/>
<table width=90%% align=left>
<tr id=samplesheet>
<td> Sample Sheet </td>
<td> <a href="SampleSheet.csv" target=SampleSheet.csv> Sample Sheet </a>  </td>
</tr>
<tr id=bclconvert>
<td> bclconvert reports  </td>
<td> <a href=bclconvert/index.html> bclconvert reports </a>  </td>
</tr>
<tr id=slippery_slope>
<td> Cumulative self-relatedness </td>
<td> <a href="file://isamba/dataset/gseq_processing/scratch/gbs/SelfRelDepth_details.html" target=slippery_slopr> Cumulative self-relatedness ~ depth </a>  </td>
</tr>
<tr id=tags_reads>
<td> Tag and Read Counts (plot) </td>
<td> <img src=tag_read_stats.jpg title=tag_read_stats.jpg/> </td>
</tr>
<tr>
<td> Tag and Read Counts (text) </td>
<td> <a href=tags_reads_cv.txt target=_blank> tags_reads_cv.txt </a>
<p/> <a href=tags_reads_summary.txt target=_blank> tags_reads_summary.txt </td>
</tr>
<tr id=barcode_yield>
<td> Barcode yield (plot) </td>
<td> <img src=barcode_yields.jpg title=barcode_yields.jpg/> </td>
</tr>
<tr>
<td> Barcode yield (text) </td>
<td> <a href=barcode_yield_summary.txt> barcode_yield_summary.txt </a> </td>
</tr>
<tr id=bwa>
<td> BWA alignment (plot) </td>
<td> <img src=mapping_stats.jpg title=mapping_stats.jpg/> </td>
</tr>
<tr>
<td> BWA alignment (text) </td>
<td> <a href=stats_summary.txt> bwa stats summary </a> </td>
</tr>
<tr id=fastqc>
<td> FASTQC </td>
<td> <a href=fastqc> FASTQC results </a> </td>
</tr>
<tr id=multiqc>
<td> MULTIQC </td>
<td> <a href=multiqc> MULTIQC (mashup of FASTQC across lanes) </a> </td>
</tr>
<tr id=raw_kmer>
<td> 6-mer distributions (raw data)</td>
<td>
<img src=kmer_analysis/kmer_entropy.k6A.jpg title=kmer_entropy.k6A.jpg height=600 width=600/>
<img src=kmer_analysis/kmer_zipfian_comparisons.k6A.jpg title=kmer_zipfian_comparisons.k6A.jpg  height=400 width=400/>
<a href=kmer_analysis/heatmap_sample_clusters.k6A.txt> Clusters  </a>
</td>
</tr>
<tr id=trimmed_kmer>
<td> 6-mer distributions (GBS-adapter-trimmed data)</td>
<td>
<img src=trimmed_kmer_analysis/kmer_entropy.k6.jpg title=kmer_entropy.k6.jpg height=600 width=600/>
<img src=trimmed_kmer_analysis/kmer_zipfian_comparisons.k6.jpg title=kmer_zipfian_comparisons.k6.jpg  height=400 width=400/>
<a href=trimmed_kmer_analysis/heatmap_sample_clusters.k6.txt> Clusters  </a>
</td>
</tr>
</table>
<p/>
"""


footer1="""
</body>
</html>
"""

def get_cohorts(options):
    BASEDIR=options["basedir"]
    # cohorts are idenitified as subfolders of the run folder that
    # * are not tardis working folders (i.e. have names starting with tardis
    # * are of like SQ0775.all.TILAPIA.PstI-MspI
    #   - i.e. library.qc-cohort.gbs-cohort.enzyme
    run_folder=os.path.join(BASEDIR, options["run_folder"])
    #print "DEBUG1 : "+run_folder
    #SQ0810.all.PstI-MspI.PstI-MspI
    #SQ0812.all.ApeKI.ApeKI
    #SQ2768.all.ApeKI.ApeKI
    #SQ2769.all.ApeKI.ApeKI
    #SQ2770.all.ApeKI.ApeKI

    cohort_folders=[ node for node in os.listdir(run_folder) if re.search("^tardis", node) is None and  re.search("^OLD", node) is None and\
                     re.search("^\S+\.\S+\.\S+\.\S+$", node) is not None and os.path.isdir(os.path.join(run_folder, node)) ]
    
    #print "DEBUG2 : %s" + str(cohort_folders)
    return cohort_folders
   
    
    
def generate_run_plot(options):
    BASEDIR=options["basedir"]   # e.g. /bifo/scratch/hiseq/postprocessing/gbs
    stats = {
        "found file count" : 0,
        "no file count" : 0,
        "no sample count" : 0
    }

    file_group_iter = ( ("Demultiplex (text file links)", "link"),("Deduplication","in-line"),("Overall SNP yields", "in-line"), \
                       ("KGD stdout", "in-line"),("KGD (plots)", "image"), ("KGD details (text file links)", "link"), \
                       ("GUSbase (plots)", "image"), ("GUSbase (text file links)", "link"), \
                       ("Preview common sequence (trimmed fastq)", "in-line"), ("All common sequence (trimmed fastq)", "link"), \
                       ("Preview common sequence (low depth tags)", "in-line"), ("All common sequence (low depth tags)", "link"), \
                       ("Low depth tag kmer summary (plots)", "image"), ("Low depth tag kmer summary (text file links)", "link"),\
                       ("All tag kmer summary (plots)", "image"), ("All tag kmer summary (text file links)", "link"),\
                       ("Low depth tag nt blast summary (plots)", "image"), ("Low depth tag nt blast summary (text file links)", "link")
                       )
    file_iters = {
        #"KGD" : ['KGD/MAFHWdgm.05.png', 'KGD/SNPDepthHist.png', 'KGD/AlleleFreq.png', 'KGD/GHWdgm.05-diag.png', 'KGD/SNPDepth.png', 'KGD/finplot.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/SampDepth.png', 'KGD/G-diag.png', 'KGD/Gdiagdepth.png', 'KGD/LRT-hist.png', 'KGD/MAF.png', 'KGD/GcompareHWdgm.05.png', 'KGD/Gcompare.png', 'KGD/SampDepthHist.png', 'KGD/CallRate.png', 'KGD/GHWdgm.05diagdepth.png', 'KGD/Heatmap-G5.png', 'KGD/SampDepth-scored.png', 'KGD/HWdisMAFsig.png', 'KGD/LRT-QQ.png', 'KGD/SampDepthCR.png', 'KGD/PC1v2G5HWdgm.05.png'],
        #"KGD plots" : ['KGD/AlleleFreq.png', 'KGD/finplot.png', 'KGD/G-diag.png', 'KGD/HWdisMAFsig.png', 'KGD/MAF.png', 'KGD/SampDepth.png', 'KGD/SNPDepth.png',
        #        'KGD/CallRate.png', 'KGD/GcompareHWdgm.05.png', 'KGD/GHWdgm.05diagdepth.png', 'KGD/LRT-hist.png', 'KGD/PC1v2G5HWdgm.05.png', 'KGD/SampDepth-scored.png'
        #        'KGD/Co-call-HWdgm.05.png', 'KGD/Gcompare.png', 'KGD/GHWdgm.05-diag.png', 'KGD/LRT-QQ.png', 'KGD/SampDepthCR.png', 'KGD/SNPCallRate.png'
        #        'KGD/Co-call-.png', 'KGD/Gdiagdepth.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/MAFHWdgm.05.png', 'KGD/SampDepthHist.png', 'KGD/SNPDepthHist.png'],
        "Demultiplex (text file links)" :  ["TagCount.csv","FastqToTagCount.stdout"],
        "Deduplication" :  ["dedupe_summary.txt"],        
        "Overall SNP yields" :  ["overall_snp_yield.txt"],
        "KGD stdout" :  ["KGD.stdout"],
        "KGD (plots)" : ['KGD/AlleleFreq.png', 'KGD/CallRate.png', 'KGD/Co-call-HWdgm.05.png', 'KGD/Co-call-.png', 'KGD/finplot.png', \
                         'KGD/GcompareHWdgm.05.png', 'KGD/Gcompare.png', 'KGD/Gdiagdepth.png', 'KGD/G-diag.png', 'KGD/GHWdgm.05diagdepth.png', \
                         'KGD/GHWdgm.05-diag.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/HWdisMAFsig.png', 'KGD/LRT-hist.png', 'KGD/LRT-QQ.png', \
                         'KGD/MAFHWdgm.05.png', 'KGD/MAF.png', 'KGD/PC1v2G5HWdgm.05.png', 'KGD/SampDepthCR.png', 'KGD/SampDepthHist.png', \
                         'KGD/SampDepth.png', 'KGD/SampDepth-scored.png', 'KGD/SNPCallRate.png', 'KGD/SNPDepthHist.png', 'KGD/SNPDepth.png', \
                         'KGD/X2star-QQ.png', 'KGD/PlateDepth.png', 'KGD/PlateInb.png', 'KGD/SubplateDepth.png', 'KGD/SubplateInb.png'],
        "GUSbase (plots)" : ['KGD/GUSbase_comet.jpg'],
        "GUSbase (text file links)" : ['KGD/GUSbase_comet.pdf'],
        "KGD details (text file links)" : ['KGD/GHW05.csv', 'KGD/GHW05-Inbreeding.csv', 'KGD/GHW05-long.csv', 'KGD/GHW05-pca_metadata.tsv', 'KGD/GHW05-pca_vectors.tsv', 'KGD/GHW05-PC.csv', 'KGD/GHW05.RData', 'KGD/GHW05.vcf', 'KGD/HeatmapOrderHWdgm.05.csv', 'KGD/HeatmapOrderHWdgm.05.csv.blinded', 'KGD/PCG5HWdgm.05.pdf', 'KGD/SampleStats.csv', 'KGD/SampleStats.csv.blinded', 'KGD/seqID.csv', 'KGD/seqID.csv.blinded'],        
        "Preview common sequence (low depth tags)" : [ 'preview_common_sequence_lowdepthtags.txt']            ,
        "All common sequence (low depth tags)" : [ 'all_common_sequence_lowdepthtags.txt']            ,        
        "Preview common sequence (trimmed fastq)" : [ 'preview_common_sequence_trimmed.txt']            ,
        "All common sequence (trimmed fastq)" : [ 'all_common_sequence_trimmed.txt']            ,        
        "Low depth tag kmer summary (plots)" : [ 'kmer_analysis/kmer_entropy.k6Aweighting_methodtag_count.jpg', 'kmer_analysis/kmer_zipfian_comparisons.k6Aweighting_methodtag_count.jpg','kmer_analysis/zipfian_distances.k6Aweighting_methodtag_count.jpg']            ,
        "Low depth tag kmer summary (text file links)" : [ 'kmer_analysis/heatmap_sample_clusters.k6Aweighting_methodtag_count.txt', 'kmer_analysis/zipfian_distances_fit.k6Aweighting_methodtag_count.txt']        ,
        "All tag kmer summary (plots)" : [ 'allkmer_analysis/kmer_entropy.k6Aweighting_methodtag_count.jpg', 'allkmer_analysis/kmer_zipfian_comparisons.k6Aweighting_methodtag_count.jpg','allkmer_analysis/zipfian_distances.k6Aweighting_methodtag_count.jpg']            ,
        "All tag kmer summary (text file links)" : [ 'allkmer_analysis/heatmap_sample_clusters.k6Aweighting_methodtag_count.txt', 'allkmer_analysis/zipfian_distances_fit.k6Aweighting_methodtag_count.txt']        ,
        "Low depth tag nt blast summary (plots)" : [ 'blast/locus_freq.jpg', 'blast/locus_freq_abundant.jpg', 'blast/taxonomy_summary_profile.jpg', 'blast/taxonomy_summary_variable.jpg'],
        "Low depth tag nt blast summary (text file links)" : [ 'blast/locus_freq.txt', 'blast/frequency_table.txt', 'blast/taxonomy_summary_profiles.heatmap_clusters.txt', 'blast/taxonomy_summary_variable.heatmap_clusters.txt']
    }

    
    with open(options["output_filename"],"w") as out_stream:

        print >> out_stream, header1%options

        print >> out_stream, overview_section

        #print "DEBUG : calling get_cohorts"
        cohorts = get_cohorts(options)

        print >> out_stream, "<a id=lane_plots />\n"        
        print >> out_stream, "<a id=sample_plots />\n<a id=cohort_plots />\n"
        for (file_group, file_type)  in file_group_iter:
            # output overall header for file group
            print >> out_stream, """
<table width=90%% align=left>
<tr>
<td><h2> %s </h2></td>
</tr>
</table>"""%file_group
            # output cohort column headings
            print >> out_stream, "<table width=90%% align=left>\n", \
                                 "<tr>\n", \
                                 "<td> <h4> Name </h4> </td>\n",\
                                 "\n".join(["<td><h4> %s </h4></td>"%cohort for cohort in cohorts]), \
                                 "\n</tr>\n"
            for file_name in file_iters[file_group]:

                print >> out_stream , "<tr><td>%s</td>\n"%file_name
                for cohort in cohorts:
                    file_path = os.path.join(BASEDIR, options["run_folder"], cohort, file_name)
                    alt_file_path=os.path.join(BASEDIR, options["run_folder"], "html", cohort, file_name)

                    if file_type == "image":
                        image_relpath=os.path.join(cohort, file_name)

                        if os.path.exists(file_path):
                            print >> out_stream, "<td> <img src=%s title=%s height=300 width=300/> </td>\n"%(image_relpath, file_path)
                        else:
                            print >> out_stream, "<td> unavailable </td>\n"
                    elif file_type == "link":
                        link_relpath=os.path.join(cohort, file_name)

                        if file_group in ["Preview common sequence (trimmed fastq)", "All common sequence (trimmed fastq)" , "Preview common sequence (low depth tags)", "All common sequence (low depth tags)"]:
                            file_path=os.path.join(BASEDIR, options["run_folder"], "common_sequence", cohort, file_name)
                            link_relpath=os.path.join(cohort, "common_sequence", file_name)

                        if os.path.exists(file_path) or os.path.exists(alt_file_path):
                            print file_path
                            print >> out_stream, "<td width=300> <a href=%s target=%s> %s </a></td>\n"%(link_relpath, file_name, link_relpath)
                        else:
                            print >> out_stream, "<td width=300> unavailable </td>\n"
                    elif file_type == "in-line":
                        text = "(unavailable)"

                        if file_group in ["Preview common sequence (trimmed fastq)", "All common sequence (trimmed fastq)" , "Preview common sequence (low depth tags)", "All common sequence (low depth tags)"]:
                            file_path=os.path.join(BASEDIR, options["run_folder"], "common_sequence", cohort, file_name)
                        elif file_group in [ "Overall SNP yields" ]:
                            file_path=os.path.join(BASEDIR, options["run_folder"], cohort, file_name)
                        elif file_group in [ "KGD stdout","Deduplication" ]:
                            file_path=os.path.join(BASEDIR, options["run_folder"], "html", cohort, file_name)                            
                        if os.path.exists(file_path):
                            with open(file_path,"r") as infile:
                                text="\n".join((record.strip() for record in infile))
                                
                        print >> out_stream, "<td id=\"%s\"> <font size=-2> <pre>%s</pre> </font> </td>"%(file_group,text)
                            
                print >> out_stream , "</tr>\n"
            print >> out_stream, "</table>\n"



        print >> out_stream, footer1



    print stats
                
                
def get_options():
    description = """
    """
    long_description = """
example :

./make_cohort_pages.py -r 181012_D00390_0409_ACCWRRANXX -o /dataset/gseq_processing/scratch/gbs/181012_D00390_0409_ACCWRRANXX/html/peacock.html
key file summary looks like :

run     run_number      lane    samplename      species file_name
140624_D00390_0044_BH9PEBADXX   0044    1       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140624_D00390_0044_BH9PEBADXX   0044    2       SQ0001  Deer    140624_D00390_0044_BH9PEBADXX.gbs/SQ0001.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209    1       SQ0008  Deer    140904_D00390_0209_BC4U6YACXX.gbs/SQ0008.processed_sample/uneak/kmer_analysis/kmer_zipfian_comparisons.jpg
140904_D00390_0209_BC4U6YACXX   0209 

    """
    parser = argparse.ArgumentParser(description=description, epilog=long_description, formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-r', '--run_folder' , dest='run_folder', required=True, type=str, help="run name")
    parser.add_argument('-H', '--image_height' , dest='image_height', default=300, type=int, help="image height")
    parser.add_argument('-W', '--image_width' , dest='image_width', default=300, type=int, help="image width")
    parser.add_argument('-o', '--output_filename' , dest='output_filename', default="peacock.html", type=str, help="name of output file")
    parser.add_argument('-b', '--basedir' , dest='basedir', default="/dataset/gseq_processing/scratch/gbs", type=str, help="base dir of original output")

    
    args = vars(parser.parse_args())

    return args


def main():

    options = get_options()
    print options 
    generate_run_plot(options)

    
if __name__ == "__main__":
   main()



        

