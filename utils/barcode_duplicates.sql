select 
   g.flowcell,
   g.barcode,
   g.lane, 
   g.createddate,
   g.sequencing_platform,
   g.platename,
   g.platerow,
   g.platecolumn,
   g.libraryprepid,
   g.gbs_cohort,
   g.factid,
   g.sample,
   g.species,
   g.taxid,
   g.control
from gbskeyfilefact as g join (
select
   flowcell,
   libraryprepid,
   lane,
   gbs_cohort,
   barcode,
   count(*)
from 
   gbskeyfilefact 
group by 
   flowcell,
   libraryprepid,
   lane,
   gbs_cohort,
   barcode
having
   count(*) > 1 ) as d
on 
   d.flowcell = g.flowcell and
   d.libraryprepid = g.libraryprepid and
   d.lane = g.lane and 
   d.gbs_cohort = g.gbs_cohort and 
   d.barcode = g.barcode 
order by 1,2
