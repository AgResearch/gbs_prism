# gbs_prism for eRI

This branch is an embryonic port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/master) for eRI.

The design approach is as follows:
- use SnakeMake instead of Tardis
- all rule implementations use in-process invocations of Python code instead of spawning shell scripts, for richer parameter handling (rather than strings passed on command line)
- the Python library [agr](src/agr) is mostly a refactoring of existing Python code from legacy `gbs_prism` and `seq_prisms`

## Batch Mode

This is the normal way to run the pipeline, and unless there is breakage, should be all that is needed.

## Interactive Use

The `RunContext` class is useful for interactive use, as it facilitates creation of various objects, with the paths defined in the redun context file.

With the `gbs_prism` module loaded:

```
$ python
Python 3.11.10 (main, Sep  7 2024, 01:03:31) [GCC 13.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> from agr.gbs_prism.interactive import RunContext
>>> run = RunContext("./context/home.tiny.json", "240323_A01439_0249_BH33MYDRX5")

>>> run.gbs_keyfiles.create()
```

## Work in progress

The eri branch in this repo is a work-in-progress.  Eventually the Python library will be moved out as a separately installable package.

## Notes

1. historical_unblind has been omitted, seems not to be required

2. some items which were previously dumped into the filesystem are now simply passed around as lists of strings
   namely: method, bwa_references
