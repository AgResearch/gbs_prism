# gbs_prism for eRI

The `main` branch in this repo is the port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/legacy) for eRI. (The legacy branch has been retained and renamed from `master` to `legacy`.)

The design approach is as follows:
- use redun instead of Tardis
- all rule implementations use in-process invocations of Python code instead of spawning shell scripts, for richer parameter handling (rather than strings passed on command line)
- the Python library [agr](src/agr) is mostly a refactoring of existing Python code from legacy `gbs_prism` and `seq_prisms`

## Batch Mode

This is the normal way to run the pipeline, and unless there is breakage, should be all that is needed.

Currently Slurm has not been integrated, so the while pipeline runs in the foreground. (This is an early access release!)  So it;s best to run in an interactive Slurm session, as follows (for the test release).

```
login-1$ kinit
login-1$ module load gbs_prism-test
login-1$ srun -p compute --mem=256G --pty bash
compute-3$ redun run $GBS_PRISM/pipeline.py main --context-file $GBS_PRISM/eri-test.json --run 240323_A01439_0249_BH33MYDRX5
```

Note that the context file is where all path tweaking and memory sizing is done, and may be copied into the current directory for changing and using from there.

Memory usage may be high, especially:
- dedupe (150GB)

## Redun

The pipeline is built with [redun](https://insitro.github.io/redun/index.html), and that interface is exposed to users.

A useful command to examine the status of previous jobs is [`redun console`](https://insitro.github.io/redun/console.html), which uses the `.redun` directory created in the current directory when running `redun`.

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

## Development

All of the dependencies are deployed using Nix.  The best way to work on `gbs_prism` itself is in the Nix devshell using `direnv` (still yet to be deployed on eRI, sorry).  Plain old `nix develop` also works, but doesn't cache like `direnv` does, so entering the environment may be time-consuming.

## Notes

1. historical_unblind has been omitted, seems not to be required

2. some items which were previously dumped into the filesystem are now simply passed around as lists of strings
   namely: method, bwa_references
