{
  description = "Flake for gbs_prism development";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    bbmap = {
      url = "github:AgResearch/bbmap.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    bcl-convert = {
      url = "github:AgResearch/bcl-convert.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    cutadapt = {
      url = "github:AgResearch/cutadapt.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    gquery = {
      # TODO use main branch not gbs_prism branch
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/gbs_prism";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, flake-utils, bbmap, bcl-convert, cutadapt, gquery, ... }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };

          flakePkgs = {
            bbmap = bbmap.packages.${system}.default;
            bcl-convert = bcl-convert.packages.${system}.default;
            cutadapt = cutadapt.packages.${system}.default;
            gquery-api = gquery.packages.${system}.api;
            gquery-eri-dev = gquery.packages.${system}.eri-dev;
          };

          export-gquery-environment-for-eri = env:
            gquery.export-environment-for-eri.${system} env;

          devPython = pkgs.python3.withPackages (python-pkgs: [
            python-pkgs.biopython
            python-pkgs.pytest
            flakePkgs.gquery-api
          ]);

          fastq_generator =
            let
              src = pkgs.fetchFromGitHub {
                owner = "johanzi";
                repo = "fastq_generator";
                rev = "8bf8d68d0c8dc07c7e4b8c5a53068aef15b40aa6";
                hash = "sha256-XABzYER54zOipEnELhYIcOssd2GYHaKjU5K2jMt9/xc=";
              };
            in
            (pkgs.writeScriptBin "fastq_generator" (builtins.readFile "${src}/fastq_generator.py")).overrideAttrs (old: {
              buildInputs = [ pkgs.python3 ];
              buildCommand = "${old.buildCommand}\n patchShebangs $out";
            });

        in
        with pkgs;
        {
          devShells = {
            default = mkShell {
              buildInputs = [
                bashInteractive
                snakemake
                flakePkgs.bbmap
                flakePkgs.bcl-convert
                flakePkgs.cutadapt
                bwa
                fastqc
                seqtk
                gzip
                yq-go
                devPython
                graphviz # for dot, for snakemake DAG visualization

                # for fake bclconvert
                fastq_generator
              ];

              shellHook = ''
                export PYTHONPATH=./src:$PYTHONPATH
                ${export-gquery-environment-for-eri "dev"}
                export GQUERY_ROOT=$HOME/gquery-logs
              '';
            };
          };
          packages = {
            default = flakePkgs.gquery;
          };
        }
      );
}
