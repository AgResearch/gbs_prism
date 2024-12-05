process DETERMINE_COHORTS {
	tag { "${meta.id}" }

	input:
	val(meta)

	output:
	tuple val(meta), path("output/cohorts.json"), emit: cohorts

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
#!/usr/bin/env python
import os

from agr.gbs_prism.cohort_specs import gquery_cohort_specs, write_cohort_specs

os.makedirs("output", exist_ok=True)

cohort_specs = gquery_cohort_specs("${meta.run_name}")
write_cohort_specs("output/cohorts.json", cohort_specs)
"""
}
