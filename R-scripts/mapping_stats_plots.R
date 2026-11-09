#!/usr/bin/env Rscript --vanilla
#
#-------------------------------------------------------------------------
# plot the % reads mapping to the keyfile-indicated reference genome
# (ported from legacy seq_prisms mapping_stats_plots.r)
#-------------------------------------------------------------------------


get_command_args <- function() {
   args=(commandArgs(TRUE))
   summary_file <- "indicated_mapping_summary.txt"
   datafolder <- NULL
   if(length(args) < 1 || length(args) > 2){
      #quit with error message if wrong number of args supplied
      print('Usage example : Rscript --vanilla  mapping_stats_plots.R datafolder=/agr/persist/projects/2026_sequence_production_a/postprocessing/gbs/DL100022100/html [summary=indicated_mapping_summary.txt]')
      print('args received were : ')
      for (e in args) {
         print(e)
      }
      quit(status=1)
   }else{
      print("Using...")
      # seperate and parse command-line args
      for (e in args) {
         print(e)
         ta <- strsplit(e,"=",fixed=TRUE)
         switch(ta[[1]][1],
            "datafolder" = datafolder <- ta[[1]][2],
            "summary" = summary_file <- ta[[1]][2]
         )
      }
   }
   if (is.null(datafolder)) {
      print("missing datafolder=")
      quit(status=1)
   }
   return(list(datafolder=datafolder, summary_file=summary_file))
}



args <- get_command_args()

setwd(args$datafolder)
mapping_stats = read.table(args$summary_file, header=TRUE, sep="\t", quote="",
                           colClasses=c("character", "character", "character", "numeric", "numeric", "numeric"))
#cohort  sample  reference  reads  map_pct  map_std
#SQ5636.all.goat.PstI  SQ5636_DL100022100  capra_hircus_ncbi_PRJNA290100.fasta  149776  90.27  0.07

# cohorts with no indicated reference have no numbers, and are not plotted
mapping_stats <- mapping_stats[!is.na(mapping_stats$map_pct),]
mapping_stats <- mapping_stats[order(mapping_stats$map_pct),]
labels <- paste(mapping_stats$cohort, mapping_stats$reference, sep="  ")


jpeg("mapping_stats.jpg", height=max(nrow(mapping_stats), 1) *  80 + 160, width=900)

# ref
# refs for this way of doing error bars
# http://environmentalcomputing.net/single-continuous-vs-categorical-variables/
# https://stackoverflow.com/questions/13032777/scatter-plot-with-error-bars

margins=par("mar")
margins[2] = 9 * margins[2]
par(mar=margins)

#sets the bottom, left, top and right margins respectively of the plot region in number of lines of text.

if (nrow(mapping_stats) > 0) {
   mapping.plot <- barplot(mapping_stats$map_pct, names.arg = labels, horiz=TRUE, las=2,
                         xlab="Mapping %", xlim=c(0,100), cex.names = 0.8)

   lower <- mapping_stats$map_pct - mapping_stats$map_std
   upper <- mapping_stats$map_pct + mapping_stats$map_std

   arrows(lower, mapping.plot, upper, mapping.plot, angle=90, code=3, length=.1)
} else {
   plot.new()
   title(main="No mappings to a keyfile-indicated reference genome")
}
dev.off()
