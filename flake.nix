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
    tassel3 = {
      # TODO merge dev to main and use main
      url = "github:AgResearch/tassel3/dev";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    gquery = {
      # TODO use main branch not gbs_prism branch
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/gbs_prism";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, flake-utils, bbmap, bcl-convert, cutadapt, tassel3, gquery, ... }:
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
            tassel3 = tassel3.packages.${system}.default;
            gquery-api = gquery.packages.${system}.api;
            gquery-eri-dev = gquery.packages.${system}.eri-dev;
          };

          export-gquery-environment-for-eri = env:
            gquery.export-environment-for-eri.${system} env;

          devPython = pkgs.python3.withPackages (python-pkgs: [
            python-pkgs.biopython
            python-pkgs.pytest
            python-pkgs.pydantic
            flakePkgs.gquery-api
          ]);

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
                flakePkgs.tassel3
                bwa
                samtools
                fastqc
                seqtk
                gzip
                yq-go
                devPython
                graphviz # for dot, for snakemake DAG visualization
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
