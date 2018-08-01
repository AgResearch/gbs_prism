#!/bin/sh

if [ -z "$3" ]; then
   psql -U agrbrdf -d agrbrdf -h invincible -q -v run_name="'$1'" -v sample_name="'$2'" <<EOF
\t
select distinct coalesce(qc_cohort,'all') || '.' || replace(gbs_cohort, '.', '_') || '.' || replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_')  from ((biosamplelist as bsl join biosamplelistmembershiplink as l on l.biosamplelist = bsl.obid) join biosampleob as s on s.obid = l.biosampleob ) join gbskeyfilefact as g on g.biosampleob = s.obid where bsl.listname = :run_name and s.samplename = :sample_name 
EOF
else
   psql -U agrbrdf -d agrbrdf -h invincible -q -v run_name="'$1'" -v sample_name="'$2'" -v flowcell="'$3'" <<EOF
\t
select distinct coalesce(qc_cohort,'all') || '.' || replace(gbs_cohort, '.', '_') || '.' || replace(regexp_replace(regexp_replace(enzyme,'[/&]','-'),'ApeKI-MspI','MspI-ApeKI','i'),'.','_') from ((biosamplelist as bsl join biosamplelistmembershiplink as l on l.biosamplelist = bsl.obid) join biosampleob as s on s.obid = l.biosampleob ) join gbskeyfilefact as g on g.biosampleob = s.obid where bsl.listname = :run_name and s.samplename = :sample_name and g.flowcell = :flowcell
EOF
fi
