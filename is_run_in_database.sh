#!/bin/sh

################################################
# this script is deprecated. Test if a run is set up in the database like this : 
# gquery  -t lab_report -p name=illumina_run_details $RUN  > /dev/null 2>&1
# if [ $? != "0" ]; then
#    echo "run is not in databse"
# fi
#
################################################

echo "
################################################
# this script is deprecated. Test if a run is set up in the database like this :
# gquery  -t lab_report -p name=illumina_run_details \$RUN  > /dev/null 2>&1
# if [ \$? != \"0\" ]; then
#    echo \"run is not in the database\"
# fi
#
################################################
"
exit 1 

psql -U agrbrdf -d agrbrdf -h postgres -q -v run_name="'$1'" <<EOF
\t
select count(*) from biosamplelist where listname=:run_name;
EOF

