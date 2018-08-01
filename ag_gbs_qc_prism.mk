# ag_gbs_qc_prism.mk prism main makefile
#***************************************************************************************
# references:
#***************************************************************************************
# make: 
#     http://www.gnu.org/software/make/manual/make.html
#


%.ag_gbs_qc_prism:
	$*.sh
	date > $@

##############################################
# specify the intermediate files to keep 
##############################################
.PRECIOUS: %.log %.ag_gbs_qc_prism

##############################################
# cleaning - not yet doing this using make  
##############################################
clean:
	echo "no clean for now" 

