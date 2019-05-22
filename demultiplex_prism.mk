# genotype_priosm main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#


%.demultiplex_prism:
	$@.sh
	date > $@
	
##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.genotype_prism

##############################################
# cleaning - not yet doing this using make  
##############################################
clean:
	echo "no clean for now" 

