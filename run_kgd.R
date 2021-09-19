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
alleles.keep <- TRUE
functions.only <- TRUE # only load the functions from GBS-Chip-Matrix.R, do not run the standard code.


source(file.path(Sys.getenv("SEQ_PRISMS_BIN"),"/../KGD/GBS-Chip-Gmatrix.R"))
readGBS()
GBSsummary()


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
   legendpanel <- function(x = 0.5, y = 0.5, txt, cex, font) {
     text(x, y-0.1, txt, cex = cex, font = font)
     if(txt==get("labels",envir = parent.frame(n=1))[1]) collegend(coldepth) # need to get labels out of the environment of calling function
     }

   Gfull <- calcG()
   p.sep <- p; HWdis.sep <- HWdis
   seqinfo <- seq2samp(nparts=5,dfout=TRUE); colnames(seqinfo) <- c("SampleID","Flowcell","Lane","SQ","X")
   SampleIDsep <- seqinfo$SampleID
   u1 <- which(seqinfo$Lane==1)
   u2 <- which(seqinfo$Lane==2)
   issplit <- (length(u1)>0 & length(u2)>0)
   if(issplit) {
    Gsplit <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx=paste0(job,".split"),calclevel=1,puse=p.sep)
    GBSsplit <- parkGBS()
    ### sample 1 read from each lane
    depth <- 1*!is.na(samples)
    genon <- samples
    mg2 <- mergeSamples(SampleIDsep, replace=TRUE)
    SampleIDsamp <- seq2samp()
    Gdsamp <- calcGdiag(snpsubset=which(HWdis.sep > -0.05),puse=p.sep)

    activateGBS(GBSsplit)
    mg1 <- mergeSamples(SampleIDsep,replace=TRUE)
    GBSsummary()
    GHWdgm.05 <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx="HWdgm.05",npc=4,puse=p.sep)
    SampleID <- seq2samp()
    samppos <- match(SampleID,SampleIDsamp)
    Inbc <- diag(Gcomb$G5) -1
    Inbs <- Gdsamp[samppos] -1
    LaneRel <- Gsplit$G5[cbind(row=u1[match(SampleID,SampleIDsep[u1])],col=u2[match(SampleID,SampleIDsep[u2])])]

    coldepth <- colourby(sampdepth,nbreaks=40,hclpals="Teal",rev=TRUE, col.name="Depth")
    colkey(coldepth,horiz=FALSE,sfx="depth")
    bbopt <- optimise(ssdInb,lower=0,upper=200, tol=0.001,Inbtarget=Inbs,dmodel="bb", snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    NInb <- calcGdiag(snpsubset=which(HWdis.sep > -0.05),puse=p.sep)-1

    png(paste0("InbCompare",job,".png"))
    pairs(cbind(Inbc,NInb,Inbs,LaneRel-1),cex.labels=1.5, cex=1.2,
          labels=c(paste0("Combined\nmean=",signif(mean(Inbc,na.rm=TRUE),3)),
                   paste0("Combined\nalpha=",signif(bbopt$min,2),"\nmean=",signif(mean(NInb,na.rm=TRUE),3)),
                   paste0("Sampled\n1 read/lane\nmean=",signif(mean(Inbs,na.rm=TRUE),3)),
                   paste0("Between\nlane\nmean=",signif(mean(LaneRel,na.rm=TRUE)-1,3))),
          gap=0,col=coldepth$sampcol, pch=16, lower.panel=plotpanel,upper.panel=regpanel, text.panel=legendpanel, 
          main=paste("Inbreeding",job))
    dev.off()

    depth2K <<- depth2Kchoose (dmodel="bb", param=Inf)
    } else { # not split
    GHWdgm.05 <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx="HWdgm.05",npc=4,puse=p.sep)
    }
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
