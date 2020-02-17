#!/bin/sh

psql -U agrbrdf -d agrbrdf -h postgres -q -v keyfilename="'$1'" <<EOF
\t
select count(*) from datasourceob where xreflsid = :keyfilename;
EOF
