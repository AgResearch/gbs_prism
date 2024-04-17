# gbs_prism for eRI

This branch is an embryonic port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/master) for eRI.

The design approach is as follows:
- use SnakeMake instead of Tardis
- all rule implementations use Python library code instead of shell scripts
- the Python library [agr](agr) is based on repackaged existing Python code from legacy `gbs_prism`
