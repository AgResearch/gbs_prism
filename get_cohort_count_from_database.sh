#!/bin/sh

if [ -z "$3" ]; then
   psql -U agrbrdf -d agrbrdf -h postgres -q -v run_name="'$1'" -v sample_name="'$2'" <<EOF
\t
select count(distinct(coalesce(qc_cohort,'all') || '.' || replace(gbs_cohort,'.','_')||'.'||replace(enzyme,'.','_'))) from ((biosamplelist as bsl join biosamplelistmembershiplink as l on l.biosamplelist = bsl.obid) join biosampleob as s on s.obid = l.biosampleob and s.sampletype = 'Illumina GBS Library' ) join gbskeyfilefact as g on g.biosampleob = s.obid where bsl.listname = :run_name and s.samplename = :sample_name and s.sampletype = 'Illumina GBS Library'
EOF
else
   psql -U agrbrdf -d agrbrdf -h postgres -q -v run_name="'$1'" -v sample_name="'$2'" -v flowcell="'$3'" <<EOF
\t
select count(distinct(coalesce(qc_cohort,'all') || '.' || replace(gbs_cohort,'.','_')||'.'||replace(enzyme,'.','_')||'.'||coalesce(qc_cohort,'all'))) from ((biosamplelist as bsl join biosamplelistmembershiplink as l on l.biosamplelist = bsl.obid) join biosampleob as s on s.obid = l.biosampleob and s.sampletype = 'Illumina GBS Library' ) join gbskeyfilefact as g on g.biosampleob = s.obid where bsl.listname = :run_name and s.samplename = :sample_name  and s.sampletype = 'Illumina GBS Library' and g.flowcell = :flowcell
EOF
fi
