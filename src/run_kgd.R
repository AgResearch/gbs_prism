#!/usr/bin/env Rscript --vanilla

set.seed(1953) # Watson JD, Crick FH. 1953.
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
negC <- "^GBSNEG"  # not used in QC pipeline as ids are blinded
alleles.keep <- TRUE
functions.only <- TRUE # only load the functions from GBS-Chip-Matrix.R, do not run the standard code.
mindepth.bb <- 0.1  # min sampdepth (merged) for training bb model
npartsID <- 5  ## number of parts (sep by _) in a seqID

source(file.path(Sys.getenv("KGD_SRC"),"/GBS-Chip-Gmatrix.R"))
readGBS()
GBSsummary()
#------- write a version of SampleStatsRaw summed over SampleID -------
#file.rename(from="SampleStatsRaw.csv",to="SampleStatsRawSeparate.csv")
 ssraw <- read.csv("SampleStatsRaw.csv")
 ssraw$mergeID <- seq2samp(ssraw$seqID,nparts=npartsID)
 ssrawc <- aggregate(ssraw$sampdepth,by=list(SampleID=ssraw$mergeID),sum)
 colnames(ssrawc)[2] <- "sampdepth"
 write.csv(ssrawc,"SampleStatsRawCombined.csv",row.names=FALSE)

keypath <-  paste0(dirname(dirname(genofile)),"/key")
seqinfo <- read.table(paste0(keypath,"/",dir(keypath)[1]),stringsAsFactors=FALSE,header=TRUE,sep="\t")
seqinfo$keyID <- with(seqinfo,paste(sample,flowcell,lane,libraryprepid,"X4",sep="_"))
samppos <- match(seqinfo$keyID,seqID)
keypos <- match(seqID,seqinfo$keyID)
if(length(seqID.removed)>0) {
 cat("Control status of removed samples\n")
 table(seqinfo$control[match(seqID.removed,seqinfo$keyID)],useNA="always")
 }
uneg <- which(seqinfo$control[keypos]=="NEGATIVE")
if(length(uneg)>0) {
  cat("Warning: negative controls passing initial QC filters\n")
  neginfo <- negCreport(uneg)
  }
posCSampleID <- unique(seqinfo$sample[keypos][ which(seqinfo$control[keypos]=="POSITIVE")])

DO_KGD_PLATE_PLOTS <- Sys.getenv("DO_KGD_PLATE_PLOTS",unset="yes")
if((DO_KGD_PLATE_PLOTS == "yes") && any(!is.na(samppos))) { # only do it if keyfile seems to match (e.g. blinded), and it is not suppressed
  #assume only one platename
  keypos <- match(seq2samp(seqID,nparts=npartsID),seqinfo$sample)
  if(length(table(seqinfo$platename[keypos]))==1) {
   seqinfo$subplate <- (2*((match(seqinfo$row,LETTERS)+1) %% 2) + 1 + (as.numeric(seqinfo$column)+1) %% 2 )
   negpos <- seqinfo[which(seqinfo$control=="NEGATIVE"),c("row","column")]
   plateplot(plateinfo=seqinfo[keypos,],plotvar=sampdepth,vardesc="Mean Sample Depth", sfx="Depth",neginfo=negpos, vflip=TRUE)
   } else {
   cat("Multiple plates - plate plots not produced\n")
   }
} else {
  if ( DO_KGD_PLATE_PLOTS == "yes" ) {
     print("** unable to do plate plots as if(any(!is.na(samppos))) fails , from below seqinfo**")
     print(seqinfo)
  } else {
     print("** skipped plate plots as environment variable DO_KGD_PLATE_PLOTS was not set to yes **")
  }
}

if ( geno_method == "default" ) {
  legendpanel <- function(x = 0.5, y = 0.5, txt, cex, font) {
    text(x, y-0.1, txt, cex = cex, font = font)
    if(txt==get("labels",envir = parent.frame(n=1))[1]) collegend(coldepth) # need to get labels out of the environment of calling function
  }
  
  Gfull <- calcG()
  p.sep <- p; HWdis.sep <- HWdis
  seqinfosep <- seq2samp(nparts=npartsID,dfout=TRUE); colnames(seqinfosep) <- c("SampleID","Flowcell","Lane","SQ","X")
  SampleIDsep <- seqinfosep$SampleID
  u1 <- which(seqinfosep$Lane==1)
  u2 <- which(seqinfosep$Lane==2)
  nlanespersamp <- rowSums( table(SampleIDsep,seqinfosep$Lane) > 0)
  issplit <- all(seqinfosep$Lane %in% 1:2) & max(nlanespersamp) > 1
  if(issplit) {
    Gsplit <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx=".split",calclevel=1,puse=p.sep)
    GBSsplit <- parkGBS()
    ### sample 1 read from each lane
    depth <- 1*!is.na(samples)
    genon <- samples
    mg2 <- mergeSamples(SampleIDsep, replace=TRUE)
    SampleIDsamp <- seq2samp(seqID,nparts=npartsID)
    Gdsamp <- calcGdiag(snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    
    activateGBS(GBSsplit)
    GBSsummary()  # could set outlevel lower here?

# estimate bb param from single lane data compared to sampled allele from each lane  ....
    samppos1 <- match(seqinfosep$SampleID,SampleIDsamp)
    Inbs <- Gdsamp[samppos1] -1   # has sampled inbreeding 2x each indiv
    ubb <- which(sampdepth >mindepth.bb & !seqinfosep$SampleID %in% posCSampleID)  # will be 2 obs per individ (lanes 1 and 2)
    cat("Find alpha for separate lanes\n")
    bbopt <- optimise(ssdInb,lower=0,upper=200, tol=0.05,Inbtarget=Inbs[ubb],dmodel="bb", indsubset = ubb, snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    bbalpha <- c(alphaSep=bbopt$minimum) 
    # one lane at a time
    ubb0 <- ubb
    ubb <- intersect(ubb0,which(seqinfosep$Lane==1))
    cat("Find alpha for lane 1\n")
    bbopt <- optimise(ssdInb,lower=0,upper=200, tol=0.05,Inbtarget=Inbs[ubb],dmodel="bb", indsubset = ubb, snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    bbalpha <- c(bbalpha,alphaLane1=bbopt$minimum) 
    ubb <- intersect(ubb0,which(seqinfosep$Lane==2))
    cat("Find alpha for lane 2\n")
    bbopt <- optimise(ssdInb,lower=0,upper=200, tol=0.05,Inbtarget=Inbs[ubb],dmodel="bb", indsubset = ubb, snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    bbalpha <- c(bbalpha,alphaLane2=bbopt$minimum) 
    depth <- -log2(depth2Kbb(depth,alph=bbalpha[1]))  # effective depth
    mgadjdepth <- mergeSamples(SampleIDsep,replace=TRUE) # combine lanes using effective depths
    depth2K <- depth2Kchoose (dmodel="bb", param=Inf)
    SepInb <- calcGdiag(snpsubset=which(HWdis.sep > -0.05),puse=p.sep)[match(seq2samp(nparts=npartsID), SampleIDsamp)]-1

    activateGBS(GBSsplit) # depths will be recalculated here (effective depths discarded)
    mg1 <- mergeSamples(SampleIDsep,replace=TRUE)
    GBSsummary()
    GHWdgm.05 <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx="HWdgm.05",npc=4,puse=p.sep)
    SampleID <- seq2samp(seqID,nparts=npartsID)
    samppos2 <- match(SampleID,SampleIDsamp)
    Inbc <- diag(GHWdgm.05$G5) -1
    Inbs <- Gdsamp[samppos2] -1
    LaneRel <- Gsplit$G5[cbind(row=u1[match(SampleID,SampleIDsep[u1])],col=u2[match(SampleID,SampleIDsep[u2])])]
    
    ubb <- which(sampdepth>mindepth.bb & !seq2samp(nparts=npartsID) %in% posCSampleID)
    cat(length(ubb),"of",length(sampdepth),"non-control samples with depth >",mindepth.bb,"used for BB model fitting\n")
    coldepth <- colourby(sampdepth[ubb],nbreaks=40,hclpals="Teal",rev=TRUE, col.name="Depth")
    colkey(coldepth,horiz=FALSE,sfx="depth")
    cat("Find alpha for combined lanes\n")
    bbopt <- optimise(ssdInb,lower=0,upper=200, tol=0.01,Inbtarget=Inbs,dmodel="bb", snpsubset=which(HWdis.sep > -0.05),puse=p.sep)
    bbalpha <- c(bbalpha,alphaComb=bbopt$minimum) 
    print(bbalpha)
    NInb <- calcGdiag(snpsubset=which(HWdis.sep > -0.05),puse=p.sep)-1
    
    png(paste0("InbCompare",".png"),width=600, height=600,pointsize=cex.pointsize*13.5)
    pairs(cbind(Inbc,NInb,SepInb,Inbs,LaneRel-1)[ubb,,drop=FALSE],cex.labels=1.5, cex=1.2,
          labels=c(paste0("Combined\nmean=",signif(mean(Inbc[ubb],na.rm=TRUE),3)),
                   paste0("Combined\nalpha=",signif(bbalpha[4],2),"\nmean=",signif(mean(NInb[ubb],na.rm=TRUE),3)),
                   paste0("Separate\nalpha=",signif(bbalpha[1],2),"\nmean=",signif(mean(SepInb[ubb],na.rm=TRUE),3)),
                   paste0("Sampled\n1 read/lane\nmean=",signif(mean(Inbs[ubb],na.rm=TRUE),3)),
                   paste0("Between\nlane\nmean=",signif(mean(LaneRel[ubb],na.rm=TRUE)-1,3))),
          gap=0,col=coldepth$sampcol, pch=16, lower.panel=plotpanel,upper.panel=regpanel, text.panel=legendpanel, 
          main=paste("Inbreeding where depth >",mindepth.bb))
    dev.off()
    
    depth2K <- depth2Kchoose (dmodel="bb", param=Inf)
  } else { # not split
    GHWdgm.05 <- calcG(snpsubset=which(HWdis.sep > -0.05),sfx="HWdgm.05",npc=4,puse=p.sep)
  }
  writeG(GHWdgm.05, "GHW05", outtype=c(1, 2, 3, 4, 5, 6))
  writeVCF(outname="GHW05", ep=.001)
  keypos <- match(seq2samp(seqID,nparts=npartsID),seqinfo$sample)
  if((DO_KGD_PLATE_PLOTS == "yes") && any(!is.na(samppos)))  {
     if(length(table(seqinfo$platename[keypos]))==1) {
        plateplot(plateinfo=seqinfo[keypos,],plotvar=diag(GHWdgm.05$G5)-1,vardesc="Inbreeding", sfx="Inb",neginfo=negpos, colpal =rev(heat.colors(80))[25:80], vflip=TRUE)
     } else {
        cat("Multiple plates - plate plots not produced\n")
     }
  }
} else if ( geno_method == "pooled" ) {
  Gfull <- calcG(samptype=geno_method, npc=4)
  writeG(Gfull, "GFULL", outtype=c(1, 2, 3, 4, 5, 6))
  writeVCF(outname="GFULL", ep=.001)
  keypos <- match(seq2samp(seqID,nparts=npartsID),seqinfo$sample)
  if((DO_KGD_PLATE_PLOTS == "yes") && any(!is.na(samppos)))  {
     if(length(table(seqinfo$platename[keypos]))==1) {
        plateplot(plateinfo=seqinfo[keypos,],plotvar=diag(Gfull$G5)-1,vardesc="Inbreeding", sfx="Inb",neginfo=negpos, colpal =rev(heat.colors(80))[25:80], vflip=TRUE)
     } else {
        cat("Multiple plates - plate plots not produced\n")
     }
  }
  print("(not running HWdgm.05 filtering on pooled data)")
} else {
  stop(paste("Error: geno_method ", geno_method, " is not supported"))
} 


# save objects needed for GUSbase
print("saving objects for GUSbase")
save(alleles, nsnps, file="GUSbase.RData")
