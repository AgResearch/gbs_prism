// sanitise sample sheet
process CLEAN_SAMPLESHEET {
	input:
	path(raw)

	output:
	path("output/SampleSheet.csv")

	when:
	task.ext.when == null || task.ext.when

	script:
	"""
    #!/usr/bin/env python
	import os
	from agr.seq.sample_sheet import SampleSheet

	sample_sheet = SampleSheet("${raw}")
	os.makedirs("output")
	sample_sheet.write("output/SampleSheet.csv")
    """
}
