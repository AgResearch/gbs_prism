#!/bin/sh

psql -U agrbrdf -d agrbrdf -h postgres -q -v run_name="'$1'" <<EOF
\t
select count(*) from biosamplelist where listname=:run_name;
EOF

