#!/usr/bin/env python

import sys
from typing import TextIO


def get_reads_tags_per_sample(in_f: TextIO, out_f: TextIO):
    outline = ""

    _ = out_f.write("sample,flowcell,lane,sq,tags,reads\n")

    cellline = ""  # ensure initialised
    for line in in_f:
        line = line.strip()
        if "Reading FASTQ file:" in line:
            basename = line.split("/")[-1]
            components = basename.split("_")
            sq = components[0].replace("SQ00", "")
            flowcell = components[1]
            lane = components[3]
            cellline = "%s,%s,%s" % (flowcell, lane, sq)
        elif "Total number of reads in lane" in line:
            line = line.split("=")
            _ = out_f.write("total,%s,,%s\n" % (cellline, line[-1]))
        elif "Total number of good barcoded reads" in line:
            line = line.split("=")
            _ = out_f.write("good,%s,,%s\n" % (cellline, line[-1]))
            cellline = ""
        elif "will be output to" in line:
            sample = line.split("tagCounts/")[-1]
            sampleID = sample.split("_")[0]
            flowcell = sample.split("_")[1]
            lane = sample.split("_")[2]
            sq = sample.split("_")[3]
            outline = "%s,%s,%s,%s" % (sampleID, flowcell, lane, sq)
        elif not outline == "":
            line = line.split()
            outline += ",%s,%s" % (line[1], line[6])
            _ = out_f.write("%s\n" % outline)
            outline = ""
        else:
            pass


def main():
    get_reads_tags_per_sample(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
