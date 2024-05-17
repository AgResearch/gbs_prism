# gbs_prism for eRI

This branch is an embryonic port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/master) for eRI.

The design approach is as follows:
- use SnakeMake instead of Tardis
- all rule implementations use in-process invocations of Python code instead of spawning shell scripts, for richer parameter handling (rather than strings passed on command line)
- the Python library [agr](src/agr) is mostly a refactoring of existing Python code from legacy `gbs_prism` and `seq_prisms`

## Work in progress

The eri branch in this repo is a work-in-progress.  Eventually the Python library will be moved out as a separately installable package.
