print("in run_kgd.R")
print("args  :")
args = commandArgs(trailingOnly=TRUE)
print(args[1])


gform <- "uneak"
genofile <- args[1]
source(file.path(Sys.getenv("SEQ_PRISMS_BIN"),"/../KGD/GBS-Chip-Gmatrix.R"))
Gfull <- calcG()
GHWdgm.05 <- calcG(which(HWdis > -0.05),"HWdgm.05", npc=4)  # recalculate using Hardy-Weinberg disequilibrium cut-off at -0.05

G5 <- GHWdgm.05$G5
sampleID  <- read.table(text=seqID,sep="_",fill=TRUE)[,1]  ###This takes the first part of the ID before a '_'. Input from UNEAK is something like sample_flowcell_lane_library...
save(G5,sampleID,file="GHW05.RData")
write.csv(G5, "GHW05.csv", row.names=F)
