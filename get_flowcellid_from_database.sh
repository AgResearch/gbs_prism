#!/bin/sh

psql -U agrbrdf -d agrbrdf -h invincible -q -v run_name="'$1'" -v sample_name="'$2'" <<EOF
\t
select max(fcid) from hiseqsamplesheetfact h join biosamplelist b on h.biosamplelist = b.obid where b.listname = :run_name and h.sampleid = :sample_name ;
EOF
