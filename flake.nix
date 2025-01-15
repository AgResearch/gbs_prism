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
      url = "github:AgResearch/tassel3/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    kgd = {
      url = "github:AgResearch/KGD?ref=refs/tags/v1.3.0";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    GUSbase = {
      url = "github:tpbilton/GUSbase";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    gquery = {
      # TODO use main branch not gbs_prism branch
      url = "git+ssh://k-devops-pv01.agresearch.co.nz/tfs/Scientific/Bioinformatics/_git/gquery?ref=refs/heads/gbs_prism";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, flake-utils, bbmap, bcl-convert, cutadapt, tassel3, kgd, GUSbase, gquery, ... }:
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
            kgd-src = kgd.packages.${system}.src;
            GUSbase = GUSbase.packages.${system}.default;
            gquery-api = gquery.packages.${system}.api;
            gquery-eri-dev = gquery.packages.${system}.eri-dev;
          };

          export-gquery-environment-for-eri = env:
            gquery.export-environment-for-eri.${system} env;

          gbs-prism-api = with pkgs;
            python3Packages.buildPythonPackage {
              name = "gbs-prism-api";
              src = ./.;
              pyproject = true;

              nativeBuildInputs = [
                hatch
                python3Packages.hatchling
              ];

              propagatedBuildInputs = with python3Packages;
                [
                  biopython
                  pdf2image
                  pytest
                  pydantic
                  flakePkgs.gquery-api
                ];
            };

          run_kgd = pkgs.stdenv.mkDerivation {
            name = "gbs_prism_kgd";

            src = ./src/run_kgd.R;

            buildInputs = [ flakePkgs.kgd-src ];
            nativeBuildInputs = [ pkgs.makeWrapper ];

            dontUnpack = true;
            dontBuild = true;

            installPhase = ''
              mkdir -p $out/bin
              runHook preInstall
              cp $src $out/bin/run_kgd.R
              chmod 755 $out/bin/run_kgd.R
              runHook postInstall
            '';

            postFixup = ''
              wrapProgram $out/bin/run_kgd.R --set KGD_SRC "${flakePkgs.kgd-src}"
            '';
          };

          R-with-GUSbase = pkgs.rWrapper.override {
            packages = [ flakePkgs.GUSbase ];
          };

          run_GUSbase =
            pkgs.stdenv.mkDerivation {
              name = "gbs_prism_GUSbase";

              src = ./src/run_GUSbase.R;

              buildInputs = [ R-with-GUSbase ];

              dontUnpack = true;
              dontBuild = true;

              installPhase = ''
                mkdir -p $out/bin
                runHook preInstall
                cp $src $out/bin/run_GUSbase.R
                chmod 755 $out/bin/run_GUSbase.R
                runHook postInstall
              '';
            };

          python-with-gbs-prism = pkgs.python3.withPackages (python-pkgs: [
            gbs-prism-api
          ]);

          gbs-prism = pkgs.symlinkJoin
            {
              name = "gbs-prism";
              paths = [
                python-with-gbs-prism
                run_kgd
                run_GUSbase
              ] ++ [
                bbmap
                bcl-convert
                cutadapt
                tassel3
              ] ++ (with pkgs; [
                bwa
                samtools
                fastqc
                seqtk
                gzip
              ]);
            };

        in
        with pkgs;
        {
          devShells = {
            default = mkShell {
              buildInputs =
                # until we consume gbs_prism as a package we need to wrap the scripts here
                # let
                #   kmer_prism = pkgs.writeScriptBin "kmer_prism"
                #     (builtins.readFile ./src/agr/gbs_prism/kmer_prism.py);
                #   get_reads_tags_per_sample = pkgs.writeScriptBin "get_reads_tags_per_sample"
                #     (builtins.readFile ./src/agr/gbs_prism/get_reads_tags_per_sample.py);
                #   summarise_read_and_tag_counts = pkgs.writeScriptBin "summarise_read_and_tag_counts"
                #     (builtins.readFile ./src/agr/gbs_prism/summarise_read_and_tag_counts.py);
                #   make_cohort_pages = pkgs.writeScriptBin "make_cohort_pages"
                #     (builtins.readFile ./src/agr/gbs_prism/make_cohort_pages.py);
                # in
                [
                  bashInteractive
                  python3Packages.pip # for redun from a virtualenv
                  virtualenv
                  gbs-prism
                  # own package scripts, just until we consume gbs_prism as a package:
                  # kmer_prism
                  # get_reads_tags_per_sample
                  # summarise_read_and_tag_counts
                  # make_cohort_pages
                  # devtools:
                  # yq-go
                ];

              shellHook = ''
                # enable use of gbs_prism from current directory during development
                export PYTHONPATH=$(pwd)/src:$PYTHONPATH
                ${export-gquery-environment-for-eri "dev"}
                export GQUERY_ROOT=$HOME/gquery-logs
              '';
            };
          };
          packages = {
            default = gbs-prism;
          };
        }
      );
}
