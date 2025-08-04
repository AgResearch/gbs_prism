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
login-1$ module load gbs_prism   # or gbs_prism-dev or gbs_prism-test
login-1$ redun run $GBS_PRISM/pipeline.py main --run 240323_A01439_0249_BH33MYDRX5
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

## Postgres Backend

All production runs now store their redun state in the `gbs_prism_redun` database on `molten`.  This means that users will see a common history of runs when using `redun console`.

Authorisation for database access is by Kerberos ticket as for the other databases.  The host is `n-db-molten-[dtp]1`, database `gbs_prism_redun` and role `gbs_prism_redun`.

In dev and test, the default is to continue with a local SQLite database, for ease of purging redun database state.  If desired, the Postgres backend may be selected by setting the environmemt variable `REDUN_CONFIG` to `$(pwd)/config/redun.dev` or `$(pwd)/config/redun.test`.

When switching GQuery environments for development as described below, when switching to the `prod` environment, the `prod` Postgres backend will be activated (by automatically setting `REDUN_CONFIG`), and when switching to the other environments the local SQLite backend will be selected (by unsetting `REDUN_CONFIG`.)  See the content of e.g. `$GBS_PRISM_PROD_ENV` to understand how this works.

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

However, in case of needing access to other GQuery environments, they may be loaded up and confirmed as follows.  Note that since adding the Postgres database backends there is additional `gbs_prism` specific configuration to switch, so the environment variables have been changed from `GQUERY` prefixed ones to `GBS_PRISM` prefixed.

```
source $GBS_PRISM_TEST_ENV
gquery -t info
```

The other environments are available via `GBS_PRISM_DEV_ENV` and `GBS_PRISM_PROD_ENV`.

## Release Process

`gbs_prism` is installed as an environment module on eRI in `/agr/persist/apps/eri_rocky8`.  There is an [install script](eri/install) which is usually run from the Nix flake app `eri-install`.

The release process is as follows:

1. Create a release branch from latest commit on main, e.g. `release-2.3.0`
2. On the release branch, in [pyproject.toml](pyproject.toml) set the version to some alpha version e.g. `2.3.0a4`, push this change to the branch, create a git tag `2.3.0a4` for that alpha version, and push the git tag
3. Install the module under your home directory (below)
4. Verify all is well by loading the module from there
5. If not OK, go to step 2 with fixes and bump version to e.g. `2.3.0a4`
6. On the release branch, update version in [pyproject.toml](pyproject.toml) to release e.g. `2.3.0`, push new commit to this branch
7. Merge release branch to main with a PR
8. Tag e.g. `2.3.0` on main branch after merging
9. Install the module publicly (below)

[Python packaging version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-specifiers) look like `2.3.0a1`, `2.3.0a2` for alpha releases and `2.3.0` for actual releases.

The eRI module installer is available as a Nix Flake app, so the install process for the end-user facing environment module and script is as follows, and should be done on `login-1` for faster Nix build.

To install in your home directory (for testing prior to general release):

```
login-1$ export FLAKE_URI='github:AgResearch/gbs_prism?ref=refs/tags/2.3.0a4'

login-1$ nix run "${FLAKE_URI}#eri-install" -- --dev --home $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --test --home $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --home $FLAKE_URI
```


```
login-1$ export FLAKE_URI='github:AgResearch/gbs_prism?ref=refs/tags/2.3.0'

login-1$ nix run "${FLAKE_URI}#eri-install" -- --dev $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --test $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- $FLAKE_URI
```

To load the module from there, prepend `$MODULEPATH` with `~/modulefiles`.

## Notes

1. historical_unblind has been omitted, seems not to be required
