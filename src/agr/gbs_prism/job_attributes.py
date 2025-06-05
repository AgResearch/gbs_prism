def job_attributes_for_run(run: str) -> dict[str, str]:
    """To annotate a PSI/J (Slurm) job with the run name in the comment field."""
    return {"comment": run}


def job_attributes_for_cohort(run: str, cohort_name: str) -> dict[str, str]:
    """To annotate a PSI/J (Slurm) job with the run name and cohort in the comment field."""
    return {"comment": f"{run}.{cohort_name}"}
