set.seed(1944) # Avery OT, Macleod CM, McCarty M. 1944.
library(GUSbase)
print("in run_GUSbase.R")
print("args  :")
args = commandArgs(trailingOnly=TRUE)
print(args[1])

GUSdata  <- args[1]

load(GUSdata)

ref = alleles[, seq(1, 2 * nsnps - 1, 2)]
alt = alleles[, seq(2, 2 * nsnps, 2)]

GUSbase::cometPlot(ref, alt, maxdepth=500, maxSNPs=1e6)

#	maxdepth: Controls the maximum depth displayed on the axis. This can be quite good if there are only a few really large read depths, then it can save a lot of computational time.  
#	maxSNPs: Maximum number of SNPs used to generate the comet plot. If there are more SNPs than this number, then a random selection will be taken. This can be quite good for reducing the computational time.
# ref https://rdrr.io/github/tpbilton/GUSbase/man/DiagPlots.html
