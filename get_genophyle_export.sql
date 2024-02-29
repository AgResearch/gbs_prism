select  distinct     
 k.sample,
 k.flowcell,
 k.lane    ,
 k.libraryprepid   ,
 k.platename        ,
 k.platerow          ,
 k.platecolumn        ,
 k.enzyme              ,
 k.barcode              ,
 k.windowsize,
 k.species               ,
 substr(coalesce(qc_cohort, k.comment, ''),1,50) as assay_comment  ,
 y.tag_count,
 y.read_count,
 y.callrate,
 y.sampdepth,
 k.createddate,
 replace(k.fastq_link,'/dataset/hiseq/active/fastq-link-farm/','') as fastq_link
from
 (gbskeyfilefact as k join biosampleob as b on b.obid = k.biosampleob ) left outer join gbsyieldfact as y on
 ( k.qc_sampleid = y.sampleid or k.sample = y.sampleid) and
 k.flowcell = y.flowcell and
 k.lane = y.lane and
 k.libraryprepid = y.sqnumber and
 y.cohort = b.samplename || '.all.' || k.gbs_cohort || '.' || k.enzyme 
