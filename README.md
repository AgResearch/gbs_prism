# gbs_prism for eRI

The `main` branch in this repo is the port of legacy HPC [gbs_prism](https://github.com/AgResearch/gbs_prism/tree/legacy) for eRI. (The legacy branch has been retained and renamed from `master` to `legacy`.)

The design approach is as follows:
- use redun instead of Tardis
- all rule implementations use in-process invocations of Python code instead of spawning shell scripts, for richer parameter handling (rather than strings passed on command line)
- the Python library [agr](src/agr) is mostly a refactoring of existing Python code from legacy `gbs_prism` and `seq_prisms`

## Usage

This is the normal way to run the pipeline, and unless there is breakage, should be all that is needed.

The pipeline uses the cluster configuration in `$GBS_PRISM_EXECUTOR_CONFIG`, which is expected to point at a valid [Jsonnet](https://jsonnet.org/) file.
To see the post-processed configuration, view the output of `jsonnet $GBS_PRISM_EXECUTOR_CONFIG`.

```
login-1$ kinit
login-1$ module load gbs_prism-test
login-1$ redun run $GBS_PRISM/pipeline.py main --context-file $GBS_PRISM/eri-test.json --run 240323_A01439_0249_BH33MYDRX5
```

There is no need to have a local copy of the repo if simply running the pipeline from the environment module like this (but see note on development, below).

Note that the context file is where all path tweaking and memory sizing is done, and may be copied into the current directory for changing and using from there.

Memory usage may be high, especially:
- dedupe (150GB)

## Redun

The pipeline is built with [redun](https://insitro.github.io/redun/index.html), and that interface is exposed to users.

A useful command to examine the status of previous jobs is [`redun console`](https://insitro.github.io/redun/console.html), which uses the `.redun` directory created in the current directory when running `redun`.

## GQuery

When switching between `dev`, `test`, and `prod` environments, it is important not to lose track of which databases `gquery` is currently using.

This may be shown using `gquery -t info`.

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

All of the dependencies are deployed using Nix.  The best way to work on `gbs_prism` itself is in the Nix devshell using `direnv`.  When doing this, ensure you don't have any `gbs_prism` environment module loaded.

To get going with `direnv` if you don't already have it available by means of Nix Home Manager, add these lines to your `~/.bashrc`:

```
module load nix-direnv
eval "$(direnv hook bash)"
```

To hook in the optimised Nix variant of `direnv`, run these commands directly just once for initial setup:

```
mkdir -p ~/.config/direnv && rm -f ~/.config/direnv/direnvrc && echo 'source $NIX_DIRENVRC' > ~/.config/direnv/direnvrc && cat ~/.config/direnv/direnvrc
```

If this fails to print `source $NIX_DIRENVRC` perhaps you omitted the single quotes.  It is important not to expand the environment variable ahead of time.

Then, for each directory containing a `.envrc` file, you will need to `direnv allow` for it to do anything. In your interactive shell, `cd` into the top-level directory of the `gbs_prism` repo to get prompted to do this.  The first time you do this will take a long time building the Nix flake.  Ensure to do this on `login-1` which is faster by virtue of being the Nix head node.  Subsequent use is cached from `.direnv`.

When working like this, `gbs_prism` itself is made available to Python by virtue of `./src` being on the `PYTHONPATH` (which is set up by the Nix flake).  So any changes made will take immediate effect.  However, all dependencies, including `gquery` and `redun` are consumed via Nix flakes, and therefore not possible to change without rebuilding the flake.

When you change directory to anywhere other than the main repo or its children, the direnv environment is unloaded.

### GQuery environments for development

By default when working in the Nix devshell the GQuery dev environment is active.  In general, this is all that is needed and all that is appropriate.

However, in case of needing access to other GQuery environments, they may be loaded up and confirmed as follows.

```
source $GQUERY_TEST_ENV
gquery -t info
```

The other environments are available via `GQUERY_DEV_ENV` and `GQUERY_PROD_ENV`.

## Notes

1. historical_unblind has been omitted, seems not to be required
