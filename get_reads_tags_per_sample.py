#!/usr/bin/env python

infile = "UFastqToTagCount.out"
infh = open(infile)

outfile = "TagCount.csv"
ofh = open(outfile, "w")

outline = ""

print >> ofh, "sample,flowcell,lane,sq,tags,reads"

for line in infh.readlines():
	line = line.strip()
	if "Reading FASTQ file:" in line:
		line = line.split("/")
		line = line[-1]
		line = line.split("_")
		sq = line[0].replace("SQ00", "")
		flowcell = line[1]
		lane = line[3]
		cellline = "%s,%s,%s" %(flowcell, lane, sq)
	elif "Total number of reads in lane" in line:
		line = line.split("=")
		total_line = "total,%s,,%s" %(cellline, line[-1])
		print >> ofh, total_line
	elif "Total number of good barcoded reads" in line:
		line = line.split("=")
		good_line = "good,%s,,%s" %(cellline, line[-1])
		print >> ofh, good_line
		cellline = ""
		total_line = ""
		good_line = ""
	elif "will be output to" in line:
		sample = line.split('tagCounts/')[-1]
		sampleID = sample.split('_')[0]
		flowcell = sample.split('_')[1]
		lane = sample.split('_')[2]
		sq = sample.split('_')[3]
		outline = "%s,%s,%s,%s" %(sampleID, flowcell, lane, sq)
	elif not outline == "":
		line = line.split()
		outline += ",%s,%s" %(line[1], line[6])
		print >> ofh, outline
		outline = ""
	else:
		pass

infh.close()
ofh.close()
