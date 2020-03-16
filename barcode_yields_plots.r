# 
#-------------------------------------------------------------------------
# plot the % reads mappng 
#-------------------------------------------------------------------------


get_command_args <- function() {
   args=(commandArgs(TRUE))
   if(length(args)!=1 ){
      #quit with error message if wrong number of args supplied
      print('Usage example : Rscript --vanilla  barcode_yields_plots.r datafolder=/dataset/gseq_processing/scratch/gbs/200310_D00390_0538_BCE5FNANXX/html')
      print('args received were : ')
      for (e in args) {
         print(e)
      }
      q()
   }else{
      print("Using...")
      # seperate and parse command-line args
      for (e in args) {
         print(e)
         ta <- strsplit(e,"=",fixed=TRUE)
         switch(ta[[1]][1],
            "datafolder" = datafolder <- ta[[1]][2]
         )
      }
   }
   return(datafolder)
}



data_folder<-get_command_args() 

setwd(data_folder) 
barcode_yields = read.table("barcode_yield_summary.txt", header=TRUE, sep="\t")
#sample_ref      good_pct        good_std
#SQ2886  80.2707271056   0.00258529641497
#SQ2887  74.7603990784   0.00262088745101
#SQ1243  87.2703283787   0.00225369772438

barcode_yields <- barcode_yields[order(barcode_yields$good_pct),] 


jpeg("barcode_yields.jpg", height=nrow(barcode_yields) *  80, width=900)


# ref 
# refs for this way of doing error bars 
# http://environmentalcomputing.net/single-continuous-vs-categorical-variables/ 
# https://stackoverflow.com/questions/13032777/scatter-plot-with-error-bars

margins=par("mar")
margins[2] = 9 * margins[2]
par(mar=margins)

#sets the bottom, left, top and right margins respectively of the plot region in number of lines of text.

mapping.plot <- barplot(barcode_yields$good_pct, names.arg = barcode_yields$sample_ref, horiz=TRUE, las=2,
                      xlab="Good barcoded reads %", ylab = "Library",xlim=c(0,100), cex.names = 0.8)

lower <- barcode_yields$good_pct - barcode_yields$good_std
upper <- barcode_yields$good_pct + barcode_yields$good_std

#arrows(mapping.plot, lower, mapping.plot, upper, angle=90, code=3)
arrows(lower, mapping.plot, upper, mapping.plot, angle=90, code=3, length=.1)
dev.off()
