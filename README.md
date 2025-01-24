# gbs_prism for eRI

This branch is an embryonic port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/master) for eRI.

The design approach is as follows:
- use SnakeMake instead of Tardis
- all rule implementations use in-process invocations of Python code instead of spawning shell scripts, for richer parameter handling (rather than strings passed on command line)
- the Python library [agr](src/agr) is mostly a refactoring of existing Python code from legacy `gbs_prism` and `seq_prisms`

## Batch Mode

This is the normal way to run the pipeline, and unless there is breakage, should be all that is needed.

Currently Slurm has not been integrated, so the while pipeline runs in the foreground. (This is an early access release!)  So it;s best to run in an interactive Slurm session, as follows (for the test release).

```
login-1$ kinit
login-1$ module load gbs_prism-test
login-1$ srun -p compute --pty bash
compute-3$ redun run $GBS_PRISM/pipeline.py main --context-file $GBS_PRISM/eri-test.json --run 240323_A01439_0249_BH33MYDRX5
```

## Interactive Use

For interactive troubleshooting, the `RunContext` class is useful, as it facilitates creation of various objects, with the paths defined in the redun context file.

With the `gbs_prism` module loaded:

```
$ python
Python 3.11.10 (main, Sep  7 2024, 01:03:31) [GCC 13.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> from agr.gbs_prism.interactive import RunContext
>>> run = RunContext("240323_A01439_0249_BH33MYDRX5", "$GBS_PRISM/eri-test.json")

>>> run.gbs_keyfiles.create()
```

## Work in progress

The eri branch in this repo is a work-in-progress.  Eventually the Python library will be moved out as a separately installable package.

## Notes

1. historical_unblind has been omitted, seems not to be required

2. some items which were previously dumped into the filesystem are now simply passed around as lists of strings
   namely: method, bwa_references
