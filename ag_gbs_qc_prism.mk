# ag_gbs_qc_prism.mk prism main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#

########## non-standard analysis - these not (currently) part of "all" as expensive
%.taxonomy_analysis:   %.blast_analysis
	$@.sh
	date > $@

%.blast_analysis:   %.fasta_sample
	$@.sh
	date > $@

########## standard analysis 
%.all:  %.allkmer_analysis %.bwa_mapping 
	date > $@

%.allkmer_analysis:   %.kmer_analysis
	$@.sh
	date > $@

%.kmer_analysis:   %.fasta_sample
	$@.sh
	date > $@

%.fasta_sample:   %.unblind
	$@.sh
	date > $@

%.unblind:   %.kgd
	$@.sh
	date > $@

%.kgd:   %.demultiplex
	$@.sh
	date > $@

%.demultiplex:
	$@.sh
	date > $@

%.bwa_mapping:
	$@.sh
	date > $@

##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.ag_gbs_qc_prism %.blast_analysis %.kmer_analysis %.kgd %.demultiplex %.all %.fasta_sample

##############################################
# cleaning - not yet doing this using make  
##############################################
clean:
	echo "no clean for now" 

