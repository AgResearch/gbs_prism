// deployment configuration, that is, values which have no effect on pipeline ouput, only performance, etc.
{
  "clusters": {
    "default": {
      "slurm": {
        "queue": "inv-iranui",
        "log_directory": "dask.logs"
      }
    },
    "small": {
      "slurm": {
        "cores": 1,
        "processes": 1,
        "memory": "4GB"
      },
      "adapt": {
        "minimum_jobs": 1,
        "maximum_jobs": 10
      }
    },
    "large": {
      "slurm": {
        "cores": 8,
        "processes": 1,
        "memory": "128GB"
      },
      "adapt": {
        "minimum_jobs": 1,
        "maximum_jobs": 2
      }
    }
  },
  "tools": {
    "default": {
      "cluster": "small"
    },
    "dedupe":
    {
      "java_max_heap": "200G",
      "cluster": "large"
    },
    "tassel3":
    {
      "default": {
        "java_initial_heap": "512M",
        "java_max_heap": "20G",
        "cluster": "large"
      },
      "FastqToTagCount":
      {
        "java_max_heap": "5G",
        "cluster": "small"
      }
    }
  }
}
