#!/usr/bin/env python
#
# this script creates an html document for each cohort of
# a gbs run, which presents the various plots generated , and
# has links to text output

import os
import re
import argparse
from string import Template
from typing import Iterable

from agr.gbs_prism.paths import Paths

header1 = Template(
    """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
   "httpd://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
<head>
<title>
Overview of ${run_name}
</title>
</head>
<body>
<h1> Q/C Summaries for <a href="http://agbrdf.agresearch.co.nz/cgi-bin/fetch.py?obid=${run_name}&context=default">${run_name}</a> </h1>
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
)

overview_section = Template(
    """
<p/>
<table width=90%% align=left>
<tr id=samplesheet>
<td> Sample Sheet </td>
<td> <a href="${sample_sheet}" target=SampleSheet.csv> Sample Sheet </a>  </td>
</tr>
<tr id=bclconvert>
<td> bclconvert reports  </td>
<td> <a href="${bclconvert}"> bclconvert reports </a>  </td>
</tr>
<tr id=slippery_slope>
<td> Cumulative self-relatedness </td>
<td> <a href="${self_rel_depth_details}" target=slippery_slopr> Cumulative self-relatedness ~ depth </a>  </td>
</tr>
<tr id=tags_reads>
<td> Tag and Read Counts (plot) </td>
<td> <img src="${tag_read_stats}" title=tag_read_stats.jpg/> </td>
</tr>
<tr>
<td> Tag and Read Counts (text) </td>
<td> <a href="${tags_reads_cv}" target=_blank> tags_reads_cv.txt </a>
<p/> <a href="${tags_reads_summary}" target=_blank> tags_reads_summary.txt </td>
</tr>
<tr id=barcode_yield>
<td> Barcode yield (plot) </td>
<td> <img src="${barcode_yields}" title=barcode_yields.jpg/> </td>
</tr>
<tr>
<td> Barcode yield (text) </td>
<td> <a href="${barcode_yield_summary}"> barcode_yield_summary.txt </a> </td>
</tr>
<tr id=bwa>
<td> BWA alignment (plot) </td>
<td> <img src="${mapping_stats}" title=mapping_stats.jpg/> </td>
</tr>
<tr>
<td> BWA alignment (text) </td>
<td> <a href="${stats_summary}"> bwa stats summary </a> </td>
</tr>
<tr id=fastqc>
<td> FASTQC </td>
<td> <a href="${fastqc}"> FASTQC results </a> </td>
</tr>
<tr id=multiqc>
<td> MULTIQC </td>
<td> <a href="${multiqc}"> MULTIQC (mashup of FASTQC across lanes) </a> </td>
</tr>
<tr id=raw_kmer>
<td> 6-mer distributions (raw data)</td>
<td>
<img src="${kmer_entropy}" title=kmer_entropy.k6A.jpg height=600 width=600/>
<img src="${kmer_zipfian_comparisons}" title=kmer_zipfian_comparisons.k6A.jpg  height=400 width=400/>
<a href="${heatmap_sample_clusters}"> Clusters  </a>
</td>
</tr>
<tr id=trimmed_kmer>
<td> 6-mer distributions (GBS-adapter-trimmed data)</td>
<td>
<img src="${trimmed_kmer_entropy}"title=kmer_entropy.k6A.jpg height=600 width=600/>
<img src="${trimmed_kmer_zipfian_comparisons}" title=kmer_zipfian_comparisons.k6A.jpg  height=400 width=400/>
<a href="${trimmed_heatmap_sample_clusters}"> Clusters  </a>
</td>
</tr>
</table>
<p/>
"""
)


footer1 = """
</body>
</html>
"""


def first_existing_path_or_default(paths: Iterable[str], default: str) -> str:
    for path in paths:
        if os.path.exists(path):
            return path
    return default


def get_cohorts(paths):
    # cohorts are idenitified as subfolders of the run folder that
    # * are not tardis working folders (i.e. have names starting with tardis
    # * are of like SQ0775.all.TILAPIA.PstI-MspI
    #   - i.e. library.qc-cohort.gbs-cohort.enzyme
    run_folder = paths.gbs.run_root
    # print "DEBUG1 : "+run_folder
    # SQ0810.all.PstI-MspI.PstI-MspI
    # SQ0812.all.ApeKI.ApeKI
    # SQ2768.all.ApeKI.ApeKI
    # SQ2769.all.ApeKI.ApeKI
    # SQ2770.all.ApeKI.ApeKI

    cohort_folders = [
        node
        for node in os.listdir(run_folder)
        if re.search("^tardis", node) is None
        and re.search("^OLD", node) is None
        and re.search(r"^\S+\.\S+\.\S+\.\S+$", node) is not None
        and os.path.isdir(os.path.join(run_folder, node))
    ]

    # print "DEBUG2 : %s" + str(cohort_folders)
    return cohort_folders


def generate_run_plot(run_name: str, paths: Paths, out_path: str):
    stats = {"found file count": 0, "no file count": 0, "no sample count": 0}

    file_group_iter = (
        ("Demultiplex (text file links)", "link"),
        ("Deduplication", "in-line"),
        ("Overall SNP yields", "in-line"),
        ("KGD stdout", "in-line"),
        ("KGD (plots)", "image"),
        ("KGD details (text file links)", "link"),
        ("GUSbase (plots)", "image"),
        ("GUSbase (text file links)", "link"),
        ("Preview common sequence (trimmed fastq)", "in-line"),
        ("All common sequence (trimmed fastq)", "link"),
        ("Preview common sequence (low depth tags)", "in-line"),
        ("All common sequence (low depth tags)", "link"),
        ("Low depth tag kmer summary (plots)", "image"),
        ("Low depth tag kmer summary (text file links)", "link"),
        ("All tag kmer summary (plots)", "image"),
        ("All tag kmer summary (text file links)", "link"),
        ("Low depth tag nt blast summary (plots)", "image"),
        ("Low depth tag nt blast summary (text file links)", "link"),
    )
    file_iters = {
        # "KGD" : ['KGD/MAFHWdgm.05.png', 'KGD/SNPDepthHist.png', 'KGD/AlleleFreq.png', 'KGD/GHWdgm.05-diag.png', 'KGD/SNPDepth.png', 'KGD/finplot.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/SampDepth.png', 'KGD/G-diag.png', 'KGD/Gdiagdepth.png', 'KGD/LRT-hist.png', 'KGD/MAF.png', 'KGD/GcompareHWdgm.05.png', 'KGD/Gcompare.png', 'KGD/SampDepthHist.png', 'KGD/CallRate.png', 'KGD/GHWdgm.05diagdepth.png', 'KGD/Heatmap-G5.png', 'KGD/SampDepth-scored.png', 'KGD/HWdisMAFsig.png', 'KGD/LRT-QQ.png', 'KGD/SampDepthCR.png', 'KGD/PC1v2G5HWdgm.05.png'],
        # "KGD plots" : ['KGD/AlleleFreq.png', 'KGD/finplot.png', 'KGD/G-diag.png', 'KGD/HWdisMAFsig.png', 'KGD/MAF.png', 'KGD/SampDepth.png', 'KGD/SNPDepth.png',
        #        'KGD/CallRate.png', 'KGD/GcompareHWdgm.05.png', 'KGD/GHWdgm.05diagdepth.png', 'KGD/LRT-hist.png', 'KGD/PC1v2G5HWdgm.05.png', 'KGD/SampDepth-scored.png'
        #        'KGD/Co-call-HWdgm.05.png', 'KGD/Gcompare.png', 'KGD/GHWdgm.05-diag.png', 'KGD/LRT-QQ.png', 'KGD/SampDepthCR.png', 'KGD/SNPCallRate.png'
        #        'KGD/Co-call-.png', 'KGD/Gdiagdepth.png', 'KGD/Heatmap-G5HWdgm.05.png', 'KGD/MAFHWdgm.05.png', 'KGD/SampDepthHist.png', 'KGD/SNPDepthHist.png'],
        "Demultiplex (text file links)": [
            "TagCount.csv",
            "TagCountsAndSampleStats.csv",
            "FastqToTagCount.stdout",
        ],
        "Deduplication": ["dedupe_summary.txt"],
        "Overall SNP yields": ["overall_snp_yield.txt", "information_efficiency.txt"],
        "KGD stdout": ["KGD.stdout"],
        "KGD (plots)": [
            # now all created in blind and left in place
            "KGD/AlleleFreq.png",
            "KGD/CallRate.png",
            "KGD/Co-call-HWdgm.05.png",
            "KGD/Co-call-.png",
            "KGD/finplot.png",
            "KGD/GcompareHWdgm.05.png",
            "KGD/Gcompare.png",
            "KGD/Gdiagdepth.png",
            "KGD/GHWdgm.05diagdepth.png",
            "KGD/InbCompare.png",
            "KGD/Heatmap-G5HWdgm.05.png",
            "KGD/HWdisMAFsig.png",
            "KGD/MAFHWdgm.05.png",
            "KGD/MAF.png",
            "KGD/PC1v2G5HWdgm.05.png",
            "KGD/SampDepthCR.png",
            "KGD/SampDepthHist.png",
            "KGD/SampDepth.png",
            "KGD/SampDepth-scored.png",
            "KGD/SNPCallRate.png",
            "KGD/SNPDepthHist.png",
            "KGD/SNPDepth.png",
            "KGD/X2star-QQ.png",
            "KGD/PlateDepth.png",
            "KGD/PlateInb.png",
            "KGD/SubplateDepth.png",
            "KGD/SubplateInb.png",
        ],
        "GUSbase (plots)": ["KGD/GUSbase_comet.jpg"],
        "GUSbase (text file links)": ["KGD/GUSbase_comet.pdf"],
        "KGD details (text file links)": [
            "KGD/GHW05.csv",
            "KGD/GHW05-Inbreeding.csv",
            "KGD/GHW05-long.csv",
            "KGD/GHW05-pca_metadata.tsv",
            "KGD/GHW05-pca_vectors.tsv",
            "KGD/GHW05-PC.csv",
            "KGD/GHW05.RData",
            "KGD/GHW05.vcf",
            "KGD/HeatmapOrderHWdgm.05.csv",
            "KGD/HeatmapOrderHWdgm.05.csv.blinded",
            "KGD/PCG5HWdgm.05.pdf",
            "KGD/SampleStats.csv",
            "KGD/SampleStats.csv.blinded",
            "KGD/seqID.csv",
            "KGD/seqID.csv.blinded",
        ],
        "Preview common sequence (low depth tags)": [
            "preview_common_sequence_lowdepthtags.txt"
        ],
        "All common sequence (low depth tags)": [
            "all_common_sequence_lowdepthtags.txt"
        ],
        "Preview common sequence (trimmed fastq)": [
            "preview_common_sequence_trimmed.txt"
        ],
        "All common sequence (trimmed fastq)": ["all_common_sequence_trimmed.txt"],
        "Low depth tag kmer summary (plots)": [
            "kmer_analysis/kmer_entropy.k6Aweighting_methodtag_count.jpg",
            "kmer_analysis/kmer_zipfian_comparisons.k6Aweighting_methodtag_count.jpg",
            "kmer_analysis/zipfian_distances.k6Aweighting_methodtag_count.jpg",
        ],
        "Low depth tag kmer summary (text file links)": [
            "kmer_analysis/heatmap_sample_clusters.k6Aweighting_methodtag_count.txt",
            "kmer_analysis/zipfian_distances_fit.k6Aweighting_methodtag_count.txt",
        ],
        "All tag kmer summary (plots)": [
            "allkmer_analysis/kmer_entropy.k6Aweighting_methodtag_count.jpg",
            "allkmer_analysis/kmer_zipfian_comparisons.k6Aweighting_methodtag_count.jpg",
            "allkmer_analysis/zipfian_distances.k6Aweighting_methodtag_count.jpg",
        ],
        "All tag kmer summary (text file links)": [
            "allkmer_analysis/heatmap_sample_clusters.k6Aweighting_methodtag_count.txt",
            "allkmer_analysis/zipfian_distances_fit.k6Aweighting_methodtag_count.txt",
        ],
        "Low depth tag nt blast summary (plots)": [
            "blast/locus_freq.jpg",
            "blast/locus_freq_abundant.jpg",
            "blast/taxonomy_summary_profile.jpg",
            "blast/taxonomy_summary_variable.jpg",
        ],
        "Low depth tag nt blast summary (text file links)": [
            "blast/locus_freq.txt",
            "blast/frequency_table.txt",
            "blast/taxonomy_summary_profiles.heatmap_clusters.txt",
            "blast/taxonomy_summary_variable.heatmap_clusters.txt",
        ],
    }

    narratives = {
        "KGD/InbCompare.png": """
Check clumpify normalisation (deduplication) by comparing five estimates of inbreeding: a) production estimate
 b) adjust using fitted beta-binomial (bb) estimated on combined lanes c) adjust using fitted beta-binomial (bb) estimated on separate lanes d) sampling one read per lane to remove any duplication effect (used to fit bb)
 e) treat two lanes as two individuals. If the points are below the line in the first column (a .v. b,c,d,e), or alpha
 is low, our normalisation may not be aggressive enough, as production inbreeding estimate is thus higher than these other
 four methods (each of which should provide a robust estimate of inbreeding, even with un-normalised data)
""",
        "KGD/AlleleFreq.png": """
Comparisons SNP reference allele frequencies calculated 3 different ways: 1) after naively converting to genotypes, 2) based on allele counts (without any adjustment for multiple counts of the same allele), 3) as given by UNEAK (the same as method 2).
""",
        "KGD/CallRate.png": """
Histogram of call rate (proportion of SNPs scored) for each sample.
""",
        "KGD/Co-call-HWdgm.05.png": """
Shows the co-call distribution (see Co-call-.png) after applying the Hardy-Weinberg filter to SNPs and combining lanes (if relevant).
""",
        "KGD/Co-call-.png": """
The co-call plot shows the distribution (over all possible pairs) of the proportion of SNPs called in a pair of individuals.
Bimodality may indicate that the samples belong to 2+ genetically divergent clusters (low co-call rate for pairs from different clusters)
""",
        "KGD/finplot.png": """
A finplot shows raw Hardy-Weinberg disequilibrium (PAA - pA^2) against MAF for each SNP.
SNPs near the upper border tend to be mainly homozygous. This is often because they have low depth (perhaps only one allele observed).
SNPs near the lower border tend to be mainly heterozygous and may often represent duplicated regions erroneously treated as one region.
The Hardy-Weinberg filter, HWdgm.05 (Hardy-Weinberg disequilibium > -0.05) used in some analyses removes these heterozygous SNPs.
""",
        "KGD/Gcompare.png": """
Comparisons of different methods for calculating off-diagonals of the GRM. G5=KGD method, G3=KGD with single allele per genotype, G1=unadjusted (biased towards 0).
""",
        "KGD/GcompareHWdgm.05.png": """
Same as Gcompare.png plot but using only those SNPs passing the Hardy-Weinberg filter and combining lanes (if relevant)
""",
        "KGD/SampDepthHist.png": """
Distribution of sample depths. If it is not roughly unimodal, there may be contamination or a mix of different species or breeds. Also, some downstream
 pipelines use a sample-depth cutoff to filter the data, which could be confused by a multi-modal sample-depth distribution.
""",
        "KGD/Gdiagdepth.png": """
In theory self-relatedness estimated from GBS data should be uncorrelated with sample depth, so there should be neither negative nor positive trend
 in this plot. A negatively sloping trend has been nick-named a slippery slope, and means something is not quite right somewhere (with either the make-up of the original sample
 -e.g. some kind of contamination, or the enzyme digest, or size selection, or sequencing, or downstream processing). If they persist, slippery slopes need to be investigated and
 resolved
""",
        "KGD/GHWdgm.05diagdepth.png": """
This is similar to the Gdiagdepth.png plot, but 1) combining lanes (if relevant) and 2) based on a smaller set of SNPs (net of the Hardy-Weinberg filter), which eliminates some potential sources of
 correlation between self-relatedness estimates and sample depth. So this plot should exhibit less than (or the same) correlation as that plot.
""",
        "KGD/Heatmap-G5HWdgm.05.png": """
Heatmap representation of the G5 GRM.
Relatedness values are coloured from white to red (lowest to highest relatedness). Samples are ordered by a dendrogram from hierarchically clustering a distance matrix of the GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        "KGD/HWdisMAFsig.png": """
SNPs plotted as in finplot.png but coloured by an approximate depth-adjusted significance value.
""",
        "KGD/MAF.png": """
MAF distribution. Diverse populations tend to have a peak at low values of MAF.
""",
        "KGD/MAFHWdgm.05.png": """
MAF distribution of Hardy-Weinberg filtered SNPs after combining lanes (if relevant)
""",
        "KGD/PC1v2G5HWdgm.05.png": """
Principal components plot (1st 2 coordinates) of samples, based on the G5 GRM.
SNPs have been Hardy-Weinberg filterd and and lanes combined (if relevant)
""",
        "KGD/SampDepthCR.png": """
Plot of depth vs call rate for samples. This is usually a fairly tight upwardly curving line.
""",
        "KGD/SampDepthHist.png": """
Histogram of sample depths. This is usually unimodal.
""",
        "KGD/SampDepth.png": """
Plot of mean vs median sample depth.
""",
        "KGD/SampDepth-scored.png": """
Plot of mean sample depth for SNPs with at least one read for the sample against the mean sample depth including all SNPs.
""",
        "KGD/SNPCallRate.png": """
Histogram of the proportion of samples called for a SNP. There is usually a peak at a high value and tails off to the left.
""",
        "KGD/SNPDepthHist.png": """
Histogram of mean SNP depth. There are often a few SNPs with extremely high depth, while most SNPs have relatively low depth.
The SNPdepth.png plot has SNP depth log-transformed to show the distribution more clearly.
""",
        "KGD/SNPDepth.png": """
Plot of SNP call rate against (log-transformed) SNP depth. Usually a S-shaped band.
High depth low call rate SNPs may indicate diverse populations (some SNPs only seen in a subset) (and/or possibly size selection variation?)
""",
        "KGD/X2star-QQ.png": """
Quantile-quantile plot of approximate depth-adjusted Hardy-Weinberg test statistic for each SNP. A 1-1 line indicates the theoretical distribution holds.
A higher sloped straight line suggests some population structure. SNPs that plot higher than a straight line through the majority of SNPs may indicate SNPs that do not behave in a Mendelian fashion.
""",
        "KGD/PlateDepth.png": """
Plot of mean sample depth by plate position. Patterns of depth variation may represent problems with sample handling.
""",
        "KGD/PlateInb.png": """
Plot of estimated inbreeding by plate position. Patterns of inbreeding variation may represent problems with sample handling.
""",
        "KGD/SubplateDepth.png": """
The same as PlateDepth.png but with a different colour gradient for each subplate within the main plate.
""",
        "KGD/SubplateInb.png": """
The same as PlateInb.png but with a different colour gradient for each subplate within the main plate.
""",
        "KGD/GUSbase_comet.jpg": """
Plot to assess the validity of the binomial model for read count data generated using high-throughput sequencing technology.
SNPs tracking an intermediate slope (observed) may be due to non-diploid genome.  A downward diagonal streak (expected) is due to an internal cutoff and is associated with the presence of high depth SNPs
""",
        "blast/taxonomy_summary_profile.jpg": """
A heatmap visualisation of the estimated proportion of low-depth tags hitting Genbank taxa (blastn of an adapter-filtered random sample of tags, against nt).
 Poor quality samples (low tag count) have an off-white background. In this plot, each row represents a cluster of taxa
 with similar profiles, and is labelled with a representative taxname.
""",
        "blast/taxonomy_summary_variable.jpg": """
A heatmap visualisation of the estimated proportion of low-depth tags hitting a subset of Genbank taxa (the 100 most variable, from blastn of an adapter-filtered random sample of tags,
 against nt). Poor quality samples (low tag count) have an off-white background. In this plot, each row is just one labelled taxa.
 """,
        "blast/locus_freq.jpg": """
A heatmap visualisation of the estimated proportion of low-depth tags hitting specific Genbank accessions (e.g. chromosomes) (blastn of an adapter-filtered random sample of tags, against nt).
 Poor quality samples (low tag count) have an off-white background. In this plot, each row represents a cluster of accessions
 with similar profiles, and is labelled with a representative accession.
""",
        "blast/locus_freq_abundant.jpg": """
A heatmap visualisation of the estimated proportion of low-depth tags hitting a subset of specific Genbank accessions (the 40 most frequenctly hit, from blastn of an adapter-filtered random sample of tags,
 against nt). Poor quality samples (low tag count) have an off-white background. In this plot, each row is just one labelled accession.
""",
    }

    out_dir = os.path.dirname(out_path)

    with open(out_path, "w") as out_stream:

        _ = out_stream.write("%s\n" % (header1.substitute({"run_name": run_name})))

        _ = out_stream.write(
            "%s\n"
            % overview_section.substitute(
                {
                    "sample_sheet": os.path.relpath(
                        paths.seq.sample_sheet_path, out_dir
                    ),
                    "bclconvert": "bclconvert/index.html",  # TODO
                    "self_rel_depth_details": "file:#isamba/dataset/gseq_processing/scratch/gbs/SelfRelDepth_details.html",  # TODO
                    "tag_read_stats": "tag_read_stats.jpg",  # TODO
                    "tags_reads_cv": "tags_reads_cv.txt",  # TODO
                    "tags_reads_summary": "tags_reads_summary.txt",  # TODO
                    "barcode_yields": "barcode_yields.jpg",  # TODO
                    "barcode_yield_summary": "barcode_yield_summary.txt",  # TODO
                    "mapping_stats": "mapping_stats.jpg",  # TODO
                    "stats_summary": "stats_summary.txt",  # TODO
                    "fastqc": "fastqc",  # TODO
                    "multiqc": "multiqc",  # TODO
                    "kmer_entropy": "kmer_entropy.k6A.jpg",  # TODO
                    "kmer_zipfian_comparisons": "kmer_zipfian_comparisons.k6A.jpg",  # TODO
                    "heatmap_sample_clusters": "heatmap_sample_clusters.k6A.txt",  # TODO
                    "trimmed_kmer_entropy": "trimmed_kmer_analysis/kmer_entropy.k6A.jpg",  # TODO
                    "trimmed_kmer_zipfian_comparisons": "trimmed_kmer_analysis/kmer_zipfian_comparisons.k6A.jpg",  # TODO
                    "trimmed_heatmap_sample_clusters": "trimmed_kmer_analysis/heatmap_sample_clusters.k6A.txt",  # TODO
                }
            )
        )

        # print "DEBUG : calling get_cohorts"
        cohorts = get_cohorts(paths)

        _ = out_stream.write("<a id=lane_plots />\n\n")
        _ = out_stream.write("<a id=sample_plots />\n<a id=cohort_plots />\n\n")
        for file_group, file_type in file_group_iter:
            # output overall header for file group
            _ = out_stream.write(
                """
<table width=90%% align=left>
<tr>
<td><h2> %s </h2></td>
</tr>
</table>\n"""
                % file_group
            )
            # output cohort column headings
            _ = out_stream.write(
                "<table width=90%% align=left>\n"
                "<tr>\n"
                "<td> <h4> Name </h4> </td>\n"
                "%s"
                "\n</tr>\n\n"
                % "\n".join(["<td><h4> %s </h4></td>" % cohort for cohort in cohorts])
            )
            for file_name in file_iters[file_group]:

                _ = out_stream.write("<tr><td>%s</td>\n\n" % file_name)
                for cohort in cohorts:
                    # some files are created in the blind subdir, where we leave them,
                    # since gratuitous copying or linking of files is contrary to
                    # the spirit of the snake
                    file_path = first_existing_path_or_default(
                        [
                            os.path.join(
                                paths.gbs.run_root,
                                cohort,
                                subdir,
                                file_name,
                            )
                            for subdir in ["", "blind"]
                        ],
                        os.path.join(
                            paths.gbs.run_root,
                            cohort,
                            file_name,
                        ),
                    )
                    file_relpath = os.path.relpath(file_path, out_dir)

                    if file_type == "image":
                        if os.path.exists(file_path):
                            title = file_path
                            if file_name in narratives:
                                title = '"%s (%s)"' % (
                                    file_path,
                                    narratives[file_name].replace("\n", ""),
                                )
                            _ = out_stream.write(
                                "<td> <img src=%s title=%s height=300 width=300/> </td>\n\n"
                                % (file_relpath, title)
                            )
                        else:
                            _ = out_stream.write("<td> unavailable </td>\n\n")
                    elif file_type == "link":
                        if file_group in [
                            "Preview common sequence (trimmed fastq)",
                            "All common sequence (trimmed fastq)",
                            "Preview common sequence (low depth tags)",
                            "All common sequence (low depth tags)",
                        ]:
                            file_path = os.path.join(
                                paths.gbs.run_root,
                                "common_sequence",
                                cohort,
                                file_name,
                            )
                            file_relpath = os.path.relpath(file_path, out_dir)

                        if os.path.exists(file_path):
                            print(file_path)
                            _ = out_stream.write(
                                "<td width=300> <a href=%s target=%s> %s </a></td>\n\n"
                                % (file_relpath, file_name, file_relpath)
                            )
                        else:
                            _ = out_stream.write("<td width=300> unavailable </td>\n\n")
                    elif file_type == "in-line":
                        text = "(unavailable)"

                        if file_group in [
                            "Preview common sequence (trimmed fastq)",
                            "All common sequence (trimmed fastq)",
                            "Preview common sequence (low depth tags)",
                            "All common sequence (low depth tags)",
                        ]:
                            file_path = os.path.join(
                                paths.gbs.run_root,
                                "common_sequence",
                                cohort,
                                file_name,
                            )
                        elif file_group in ["Overall SNP yields"]:
                            file_path = os.path.join(
                                paths.gbs.run_root, cohort, file_name
                            )
                        elif file_group in ["KGD stdout", "Deduplication"]:
                            file_path = os.path.join(
                                paths.gbs.run_root,
                                "html",
                                cohort,
                                file_name,
                            )
                        if os.path.exists(file_path):
                            with open(file_path, "r") as infile:
                                text = "\n".join((record.strip() for record in infile))

                        _ = out_stream.write(
                            '<td id="%s"> <font size=-2> <pre>%s</pre> </font> </td>\n'
                            % (file_group, text)
                        )

                _ = out_stream.write("</tr>\n\n")
            _ = out_stream.write("</table>\n\n")

        _ = out_stream.write("%s\n" % footer1)

    print(stats)


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
    parser = argparse.ArgumentParser(
        description=description,
        epilog=long_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = parser.add_argument(
        "-r",
        "--run_folder",
        dest="run_folder",
        required=True,
        type=str,
        help="run name",
    )
    _ = parser.add_argument(
        "-H",
        "--image_height",
        dest="image_height",
        default=300,
        type=int,
        help="image height",
    )
    _ = parser.add_argument(
        "-W",
        "--image_width",
        dest="image_width",
        default=300,
        type=int,
        help="image width",
    )
    _ = parser.add_argument(
        "-o",
        "--output_filename",
        dest="output_filename",
        default="peacock.html",
        type=str,
        help="name of output file",
    )
    _ = parser.add_argument(
        "--postprocessing_root",
        dest="postprocessing_root",
        type=str,
        help="postprocessing root dir, e.g. /dataset/2024_illumina_sequencing_d/scratch/postprocessing",
    )

    args = vars(parser.parse_args())

    return args


def main():

    options = get_options()
    paths = Paths(options["postprocessing_root"], options["run_folder"])
    print(options)
    generate_run_plot(options["run_folder"], paths, options["output_filename"])


if __name__ == "__main__":
    main()
