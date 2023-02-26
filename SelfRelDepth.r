set.seed(2001) # Lander ES, et al. 2001.
##### regress self-related estimate on log sampdepth.
sampdepth.thresh <- 0.3
#functions.only <- TRUE
#source("~/GBS/Code/GBS-Chip-Gmatrix.R")
options(stringsAsFactors=FALSE)

get_command_args <- function() {
   args=(commandArgs(TRUE))
   if(length(args)!=1 ){
      #quit with error message if wrong number of args supplied
      print('Usage example : Rscript --vanilla  SelfRelDepth.r kgd_dir=/dataset/hiseq/scratch/postprocessing/180419_D00390_0357_ACCHG7ANXX.gbs/SQ0673.processed_sample/uneak/KGD')
      print('args received were : ')
      for (e in args) {
         print(e)
      }
      q()
   }else{
      #print("Using...")
      # seperate and parse command-line args
      for (e in args) {
         #print(e)
         ta <- strsplit(e,"=",fixed=TRUE)
         switch(ta[[1]][1],
            "KGDdir" = KGDdir <<- ta[[1]][2],
         )
      }
   }
}



#KGDdir <- "/dataset/hiseq/scratch/postprocessing/180419_D00390_0357_ACCHG7ANXX.gbs/SQ0673.processed_sample/uneak/KGD"
#windows:
#KGDdir <- paste0("//isamba",KGDdir)

get_command_args()
load(paste0(KGDdir,"/GHW05.RData"))
#GHW <- as.matrix(read.csv(paste0(KGDdir,"/GHW05.csv")))
sstats <-  read.csv(paste0(KGDdir,"/SampleStats.csv"))
indsubset <- which(sstats$sampdepth > sampdepth.thresh)
rellm <- lm(diag(G5)[indsubset] ~  log(sstats$sampdepth[indsubset]))
slope <- coef(rellm)[2]
pval <- anova(rellm)[1,"Pr(>F)"]
cat(KGDdir,slope,pval,"\n")

