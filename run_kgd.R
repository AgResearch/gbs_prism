print("in run_kgd.R")
print("args  :")
args = commandArgs(trailingOnly=TRUE)

if(length(args)==2 ){
   print(args[1])
   print(args[2])

   genofile <- args[1]
   geno_method <- args[2]
} else if (length(args)==1) {
   print(args[1])

   genofile <- args[1]
   geno_method <- "default"
} else {
   print('Usage example : Rscript --vanilla  run_kgd.R /dataset/gseq_processing/scratch/gbs/190912_D00390_0502_ACDT53ANXX/SQ1102.all.PstI-MspI.PstI-MspI/KGD default')
   print('args received were : ')
   for (e in args) {
      print(e)
   }
   q()
}

gform <- "uneak"
negC <- "^GBSNEG"  

source(file.path(Sys.getenv("SEQ_PRISMS_BIN"),"/../KGD/GBS-Chip-Gmatrix.R"))

keypath <-  paste0(dirname(dirname(genofile)),"/key")
seqinfo <- read.table(paste0(keypath,"/",dir(keypath)[1]),stringsAsFactors=FALSE,header=TRUE,sep="\t")
samppos <- match(seqinfo$sample,seq2samp(seqID))

if(any(!is.na(samppos))) { # only do it if keyfile seems to match (e.g. blinded)
  #assume only one platename
  keypos <- match(seq2samp(seqID),seqinfo$sample)
  seqinfo$subplate <- (2*((match(seqinfo$row,LETTERS)+1) %% 2) + 1 + (as.numeric(seqinfo$column)+1) %% 2 )
  negpos <- seqinfo[which(seqinfo$control=="NEGATIVE"),c("row","column")]
  plateplot(plateinfo=seqinfo[keypos,],plotvar=sampdepth,vardesc="Mean Sample Depth", sfx="Depth",neginfo=negpos)
} else {
  print("** unable to do plate plots as if(any(!is.na(samppos))) fails , from below seqinfo**")
  print(seqinfo)
}

if ( geno_method == "default" ) {
   Gfull <- calcG()
   GHWdgm.05 <- calcG(which(HWdis > -0.05),"HWdgm.05", npc=4)  # recalculate using Hardy-Weinberg disequilibrium cut-off at -0.05
   writeG(GHWdgm.05, "GHW05", outtype=c(1, 2, 3, 4, 5, 6))
   writeVCF(outname="GHW05", ep=.001)
   if(any(!is.na(samppos)))  plateplot(plateinfo=seqinfo[keypos,],plotvar=diag(GHWdgm.05$G5)-1,vardesc="Inbreeding", sfx="Inb",neginfo=negpos, colpal =rev(heat.colors(80))[25:80])
} else if ( geno_method == "pooled" ) {
   Gfull <- calcG(samptype=geno_method, npc=4)
   writeG(Gfull, "GFULL", outtype=c(1, 2, 3, 4, 5, 6))
   writeVCF(outname="GFULL", ep=.001)
   if(any(!is.na(samppos)))  plateplot(plateinfo=seqinfo[keypos,],plotvar=diag(Gfull$G5)-1,vardesc="Inbreeding", sfx="Inb",neginfo=negpos, colpal =rev(heat.colors(80))[25:80])
   print("(not running HWdgm.05 filtering on pooled data)")
} else {
   stop(paste("Error: geno_method ", geno_method, " is not supported"))
} 

# save objects needed for GUSbase
print("saving objects for GUSbase")
save(alleles, nsnps, file="GUSbase.RData")
