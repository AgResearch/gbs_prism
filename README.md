# gbs_prism

GBS (genotyping-by-sequencing) post-processing pipeline for eRI, built on
[redun](https://insitro.github.io/redun/index.html).

This branch processes **MGI single-end runs**. Illumina processing lives on the
`illumina` branch (release 2.6.x). This code is a port of the legacy HPC
[gbs_prism](https://github.com/AgResearch/gbs_prism/tree/legacy).

## What it does

| Stage | Steps | Output |
|---|---|---|
| 1 | Check the sample sheet and lane fastqs, wait for fastqs to finish copying, demultiplex with `splitBarcode`, FastQC, MultiQC, k-mer analysis, merge lanes per library, create GBS keyfiles | `<postprocessing_root>/mgi/<run>/` |
| 2 | Per cohort: sample + trim + BWA mapping, Tassel3 tag counting, unblinding, KGD, GUSbase, KGD report; then import results into the database | `<postprocessing_root>/gbs/<run>/<cohort>/` |
| 3 | Run-wide summaries: tags/reads, mapping stats, barcode yields | `<postprocessing_root>/gbs/<run>/html/` |
| Reports | Peacock report | `<postprocessing_root>/gbs/<run>/html/peacock.html` |
| Warehouse | Export and import into the genotype database (runs last) | `<geno_import_dir>/` |

**BWA mapping % in the peacock report.** The table and plot show each cohort mapped to
the reference genome its keyfile names. Negative controls are keyed as SHEEP, so every
cohort is also mapped to sheep. Those numbers are not in the table, but they are in
`stats_summary.txt` (linked as "all references"). A cohort with no reference in its
keyfile (e.g. microbes) shows as `(none indicated)`.

Before any cluster jobs start, stage 1 waits until the lane fastqs are complete
copies (gzip, with no unwritten end) that have stopped changing. It checks every 5
minutes and logs how far the copy has got, with an estimate of the time left.

You can launch a run **before its copy has finished**: it waits for up to 24 hours
while the copy keeps progressing, and starts by itself as soon as the copy is
complete. If the copy stops part-way (nothing written to any fastq for 5 minutes), it
stops straight away. Then it checks every fastq's md5 against the instrument's
`L0n/<run>_L0n_FileInfo.txt` (about 2 minutes for 4 lanes).

It stops with an error if:
- the sample sheet and run do not match,
- the run is paired-end,
- a lane's fastqs are missing, or are still being copied after 24 hours,
- a copy has stopped part-way ("copy stalled": re-copy those files),
- a lane has no `FileInfo.txt`, or a fastq's md5 does not match it (corrupt copy:
  re-copy the run).

## Inputs

All paths come from a **context file** (`context/eri-{dev,test,prod}.json`):

| Key | Meaning |
|---|---|
| `seq_roots` | Sequencer directories searched in order for `<root>/<run>/`. Stops with an error if the run is in two of them (a symlink to the same run is fine) |
| `sample_sheet_root` | MGI sample sheets, named `<run>.csv`. `[Header] Flowcell` must equal the run name |
| `postprocessing_root` | Where outputs are written |
| `keyfiles_dir`, `fastq_link_farm`, `gbs_backup_dir`, `geno_import_dir` | Keyfiles, fastq links, database backups, warehouse files |

The context file sets **paths only**. Which databases are used depends on the
environment you have loaded (see [Environments](#environments-and-databases)).

## Running

### Standard (environment module)

```
login-1$ kinit -r 7d                  # renewable ticket, see below
login-1$ tmux
login-1$ module load gbs_prism        # or gbs_prism-dev / gbs_prism-test
login-1$ run_gbs_prism DL100018469
```

A Kerberos ticket lasts 10 hours, and the database steps come at the end of a run. A
run launched ahead of a slow copy can outlast it. `kinit -r 7d` makes the ticket
renewable for 7 days. Before it expires (`klist` shows when), renew it from any
login-1 shell with `kinit -R`. The running pipeline picks up the renewed ticket.

`run_gbs_prism <run>` is shorthand for
`redun run $GBS_PRISM/pipeline.py main --run <run>`.

### From a local checkout (developers)

Complete [Developer setup](#developer-setup) once first. Then:

```
login-1$ kinit -r 7d
login-1$ module load nix-direnv && eval "$(direnv hook bash)"
login-1$ cd /projects/2023_sequence_production/gbs_prism   # direnv loads the dev environment
login-1$ redun run pipeline.py main --context-file context/eri-dev.json --run DL100018469
```

`--context-file` is required in a local checkout; only the module has it built in.

To run against **prod** from a local checkout:

```
login-1$ source $GBS_PRISM_PROD_ENV     # prod databases + prod redun backend
login-1$ gquery -t info                 # confirm which databases are active
login-1$ redun run pipeline.py main --context-file context/eri-prod.json --run DL100018469
```

> If `$GBS_PRISM_PROD_ENV` is sourced, a run with `eri-dev.json` still reads from **and
> writes to** the prod databases (keyfile import, KGD imports, warehouse). Only the output
> paths change.

## Reruns

redun caches every task. A rerun only repeats tasks whose inputs changed. Running a
finished run again with nothing changed is quick; only a few database lookups repeat.

A run that failed part-way resumes: finished tasks are reused, the rest run.

### After editing the sample sheet

Edit the sheet in `sample_sheet_root`, then rerun the same command. What re-runs
depends on what you changed:

- **Only `[GenerateKeyfile]`:** keyfiles are re-imported **only for the libraries
  whose rows changed**. Then only those libraries' cohorts are re-analysed.
  Demultiplexing and QC are reused.
- **Anything in `[Data]`:** this means the first demultiplexing was wrong.
  1. Remove `<postprocessing_root>/gbs/<run>/` first.
  2. Rerun. The checks, the fastq wait and lane planning run again.
  3. `splitBarcode` re-runs for each lane whose barcodes changed.
  4. **Every library** is re-imported and re-analysed, even if only a non-barcode
     column (such as `Description`) changed.
- **Nothing (or only saving the file unchanged):** nothing re-runs.

Do not use `--no-cache` to apply a sheet change. It repeats everything, including
hours of demultiplexing and all prod database imports.

> **One-off after upgrading to this version:** the first rerun of a run processed
> by an older version behaves like a `[Data]` edit, except that demultiplexing,
> lane merging, cutadapt and bwa are reused:
> - the fastq checks run again. They wait at least 5 minutes, and much longer if
>   the fastqs are on cold storage;
> - every library is re-imported;
> - every cohort's Tassel/KGD analysis re-runs;
> - all stage-2 database imports and warehousing are repeated.
>
> Don't rerun an old run casually.

Do not edit the archived copy of the sheet under the outputs; it is overwritten.

## Monitoring and troubleshooting

- **Job history:** `redun console` (see [docs](https://insitro.github.io/redun/console.html)).
- **Pipeline log:** `gbs_prism.log` in the directory you ran from.
- **Active databases:** `gquery -t info`.
- **Interactive use:** load run objects with the paths from a context file:

  ```python
  >>> from agr.gbs_prism.interactive import RunContext
  >>> run = RunContext("DL100018469", "context/eri-dev.json")
  ```

- **Cluster settings** (memory, partitions per tool) are in
  `$GBS_PRISM_EXECUTOR_CONFIG` ([Jsonnet](https://jsonnet.org/)). View with
  `jsonnet $GBS_PRISM_EXECUTOR_CONFIG`.

## Environments and databases

| Environment | Load with | gquery databases | redun state |
|---|---|---|---|
| dev (devshell default) | `source $GBS_PRISM_DEV_ENV` | dev | local SQLite `.redun/` |
| test | `source $GBS_PRISM_TEST_ENV` | test | local SQLite `.redun/` |
| prod | `source $GBS_PRISM_PROD_ENV` | prod | Postgres `gbs_prism_redun` on `n-db-molten-p1` |

- All database access uses your Kerberos ticket (`kinit`).
- Prod redun state is shared, so everyone sees the same run history in `redun console`.
- To use Postgres in dev or test, set `REDUN_CONFIG=$(pwd)/config/redun.dev` (or `redun.test`).

## Developer setup

Do this once, on `login-1` (the Nix head node; builds are faster there).

1. Get a Kerberos ticket: `kinit`
2. Make sure no `gbs_prism` module is loaded (`module purge`).
3. Run the setup script. The first run builds the Nix flake and is slow. It is safe to
   re-run. Use `--no-prebuild` to skip the build.

   ```
   login-1$ cd /projects/2023_sequence_production/gbs_prism
   login-1$ ./eri/dev-setup
   ```

4. Add these to `~/.bashrc` (or run them in each new shell):

   ```
   module load nix-direnv
   eval "$(direnv hook bash)"
   ```

5. `cd` into the repo. direnv loads the devshell; leaving the repo unloads it.

What the setup script does:
- points direnv at the Nix-optimised `direnvrc` (`source $NIX_DIRENVRC`),
- runs `direnv allow` for the repo,
- prebuilds the devshell.

In the devshell, `./src` is on `PYTHONPATH`, so code changes take effect immediately.
Dependencies (`redun`, `gquery`, tools) come from Nix and need a flake rebuild to change.

## Development

- **Tests:** `python -m pytest src`
- **Architecture, conventions, known issues:** see [CLAUDE.md](CLAUDE.md).
- **Layout:**
  - `pipeline.py`: entry point (`main`).
  - `src/agr/gbs_prism/redun/`: the stage tasks and reports.
  - `src/agr/redun/tasks/`: one task module per tool.
  - `src/agr/seq/`: sample sheets, barcodes and run checks.
  - `config/`: redun and cluster settings.
  - `context/`: paths for each environment.

## Release process

`gbs_prism` is installed as an environment module in `/agr/persist/apps/eri_rocky8`
by the [install script](eri/install), run via the flake app `eri-install`.

1. Create a release branch from `main`, e.g. `release-2.3.0`.
2. Set an alpha version in [pyproject.toml](pyproject.toml), e.g. `2.3.0a1`. Commit, push, then tag `2.3.0a1` and push the tag.
3. Install the module under your home directory (below), load it, and complete a test run.
4. If there are problems, fix them, bump the alpha (e.g. `2.3.0a2`) and repeat step 3.
5. Set the release version (e.g. `2.3.0`), push, and merge the branch to `main` with a PR.
6. Tag `2.3.0` on `main`, then install the module publicly (below).

Version format follows [Python version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-specifiers).

Install on `login-1`. For testing, install to your home directory, then add `~/modulefiles` to the start of `$MODULEPATH`:

```
login-1$ export FLAKE_URI='github:AgResearch/gbs_prism?ref=refs/tags/2.3.0a1'
login-1$ nix run "${FLAKE_URI}#eri-install" -- --dev --home $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --test --home $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --home $FLAKE_URI
```

Public install (drop `--home`):

```
login-1$ export FLAKE_URI='github:AgResearch/gbs_prism?ref=refs/tags/2.3.0'
login-1$ nix run "${FLAKE_URI}#eri-install" -- --dev $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- --test $FLAKE_URI
login-1$ nix run "${FLAKE_URI}#eri-install" -- $FLAKE_URI
```

## Notes

- `historical_unblind` from the legacy pipeline is omitted; it appears not to be needed.
