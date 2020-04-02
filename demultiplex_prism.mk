# demultiplex_prism main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#


%.demultiplex_prism:
	$@.sh > $@.mk.log 2>&1
	date > $@
	
##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.demultiplex_prism

##############################################
# cleaning - not yet doing this using make  
##############################################
clean:
	echo "no clean for now" 

