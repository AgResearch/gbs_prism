#!/usr/bin/env Rscript --vanilla
#
#
#-------------------------------------------------------------------------
# plot the tag and read mean and stddev
#-------------------------------------------------------------------------


get_command_args <- function() {
   args=(commandArgs(TRUE))
   if(length(args)!=2 ){
      #quit with error message if wrong number of args supplied
      print('Usage example : Rscript --vanilla  tag_count_plots.r infile=/dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/html/tags_reads_summary.txt  outfolder=/dataset/gseq_processing/scratch/gbs/200407_D00390_0541_BCE3EWANXX/html' )
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
            "outfolder" = outfolder <<- ta[[1]][2],
            "infile" = infile <<- ta[[1]][2]
         )
      }
   }
}

# example
#flowcell_sq_cohort      mean_tag_count  std_tag_count   min_tag_count   max_tag_count   mean_read_count std_read_count  min_read_count  max_read_count
#SQ1257.all.PstI.PstI_CE3EWANXX_SQ1257   253258.066845   29503.126706    41196   333481  700922.302139   175178.466915   50064   1315737
#SQ1258.all.PstI.PstI_CE3EWANXX_SQ1258   243487.630319   19029.8927137   40472   324748  696395.071809   115029.175347   49835   1314941
#SQ1259.all.PstI.PstI_CE3EWANXX_SQ1259   242148.553191   57613.3610063   39672   368608  689894.276596   281653.607972   54937   1606162

get_command_args()
setwd(outfolder)
read_tag_stats = read.table(infile, header=TRUE, sep="\t")
read_tag_stats <- read_tag_stats[order(read_tag_stats$cohort),]

###### tags #######

jpeg("tag_stats.jpg", height=800, width=800)

# ref
# refs for this way of doing error bars
# http://environmentalcomputing.net/single-continuous-vs-categorical-variables/
# https://stackoverflow.com/questions/13032777/scatter-plot-with-error-bars

margins=par("mar")
margins[2] = 6 * margins[2]
par(mar=margins)

#sets the bottom, left, top and right margins respectively of the plot region in number of lines of text.

#tags.plot <- barplot(read_tag_stats$mean_tag_count, names.arg = read_tag_stats$flowcell_sq_cohort, horiz=TRUE, las=2,
#                      xlab="Mean tag count", ylab = "Cohort",cex.names = 0.8, xlim=c(min(read_tag_stats$mean_tag_count - 1.01*read_tag_stats$std_tag_count) , max(read_tag_stats$mean_tag_count + 1.01*read_tag_stats$std_tag_count)))

tags.plot <- boxplot(tags~cohort, data=read_tag_stats, main="Tag counts", xlab="Tag count", ylab = "Cohort",cex.names = 0.8, horizontal=TRUE,las=1)
#lower <- read_tag_stats$mean_tag_count - read_tag_stats$std_tag_count
#upper <- read_tag_stats$mean_tag_count + read_tag_stats$std_tag_count

#arrows(mapping.plot, lower, mapping.plot, upper, angle=90, code=3)
#arrows(lower, tags.plot, upper, tags.plot, angle=90, code=3, length=.1)
dev.off()

###### reads #######

jpeg("read_stats.jpg", height=800, width=800)

# ref
# refs for this way of doing error bars
# http://environmentalcomputing.net/single-continuous-vs-categorical-variables/
# https://stackoverflow.com/questions/13032777/scatter-plot-with-error-bars

margins=par("mar")
margins[2] = 6 * margins[2]
par(mar=margins)

#sets the bottom, left, top and right margins respectively of the plot region in number of lines of text.

#tags.plot <- barplot(read_tag_stats$mean_read_count, names.arg = read_tag_stats$flowcell_sq_cohort, horiz=TRUE, las=2,
#                      xlab="Mean read count", ylab = "Cohort",cex.names = 0.8, xlim=c(min(read_tag_stats$mean_read_count - 1.01*read_tag_stats$std_read_count) , max(read_tag_stats$mean_read_count + 1.01*read_tag_stats$std_read_count)))
tags.plot <- boxplot(reads~cohort, data=read_tag_stats, main="Read counts", xlab="Read count", ylab = "Cohort",cex.names = 0.8, horizontal=TRUE,las=1)

#lower <- read_tag_stats$mean_read_count - read_tag_stats$std_read_count
#upper <- read_tag_stats$mean_read_count + read_tag_stats$std_read_count

#arrows(mapping.plot, lower, mapping.plot, upper, angle=90, code=3)
#arrows(lower, tags.plot, upper, tags.plot, angle=90, code=3, length=.1)



dev.off()

