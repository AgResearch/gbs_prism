# ag_gbs_qc_prism.mk prism main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#

########## non-standard analysis - these not (currently) part of "all" as expensive
%.annotation:   %.blast_analysis
	$@.sh > $@.mk.log 2>&1
	date > $@

%.blast_analysis:   %.fasta_sample
	$@.sh > $@.mk.log 2>&1
	date > $@

######### ( only applicable if kmer_analysis , allkmer_analysis or annotation have been done but we don't want to trigger a build of those
######### so handle dependency outside make )
%.unblinded_plots:
	$@.sh > $@.mk.log 2>&1
	date > $@

########## standard analysis 
########## minimal standard analysis
# this is a minimal "all" e.g. enough to get results imported to database. If needing to catch up or do minimal processing, uncomment this
# and comment out the next definition of "all"
%.all:  %.unblind  %.bwa_mapping
	date > $@


######### full standard analysis
# this is the full "all" which is usually in force. If , say, processing is behind (e.g. fault with compute or sequencing) and you are in a hurry,
# comment out this definition of "all" and uncomment the above minimal standard analysis
#%.all:  %.allkmer_analysis %.common_sequence 
#	date > $@

%.allkmer_analysis:   %.kmer_analysis
	$@.sh > $@.mk.log 2>&1
	date > $@

%.kmer_analysis:   %.fasta_sample
	$@.sh > $@.mk.log 2>&1
	date > $@

%.common_sequence:  %.bwa_mapping %.fasta_sample
	$@.sh > $@.mk.log 2>&1
	date > $@

%.fasta_sample:   %.unblind
	$@.sh > $@.mk.log 2>&1
	date > $@

%.unblind:   %.kgd
	$@.sh > $@.mk.log 2>&1
	date > $@

%.historical_unblind:   %.kgd
	$@.sh > $@.mk.log 2>&1
	date > $@

%.filtered_kgd:   %.demultiplex
	$@.sh > $@.mk.log 2>&1
	date > $@

%.kgd:   %.demultiplex
	$@.sh > $@.mk.log 2>&1
	date > $@

%.demultiplex:
	$@.sh > $@.mk.log 2>&1
	date > $@

%.fasta_demultiplex:
	$@.sh > $@.mk.log 2>&1
	date > $@

%.bwa_mapping:
	$@.sh > $@.mk.log 2>&1
	date > $@

.PHONY: %.clean
%.clean: 
	$@.sh > $@.mk.log 2>&1


##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.ag_gbs_qc_prism %.blast_analysis %.kmer_analysis %.allkmer_analysis %.kgd %.demultiplex %.all %.fasta_sample %.bwa_mapping %.unblind %.allkmer_analysis %.annotation %.common_sequence
