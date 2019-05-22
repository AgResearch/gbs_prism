print("in run_kgd.R")
print("args  :")
args = commandArgs(trailingOnly=TRUE)
print(args[1])


gform <- "uneak"
genofile <- args[1]
source(file.path(Sys.getenv("SEQ_PRISMS_BIN"),"/../KGD/GBS-Chip-Gmatrix.R"))
Gfull <- calcG()
GHWdgm.05 <- calcG(which(HWdis > -0.05),"HWdgm.05", npc=4)  # recalculate using Hardy-Weinberg disequilibrium cut-off at -0.05


#To save a G Matrix
writeG(GHWdgm.05, "GHW05", outtype=c(1, 2, 3, 4, 5, 6))

#To write out vcf file
writeVCF(outname="GHW05", ep=.001)
