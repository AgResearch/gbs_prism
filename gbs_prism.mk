# gbs_prism main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#


%.gbs_prism:
	$*.sh
	date > $@

%.demultiplex_prism:
	$*.sh
	date > $@
	
##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.gbs_prism

##############################################
# cleaning - not yet doing this using make  
##############################################
clean:
	echo "no clean for now" 

