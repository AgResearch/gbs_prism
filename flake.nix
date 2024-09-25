{
  description = "Flake for gbs_prism development";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    bcl-convert = {
      url = "github:AgResearch/bcl-convert.nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, bcl-convert, ... }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };

          flakePkgs = {
            bcl-convert = bcl-convert.packages.${system}.default;
          };

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
                flakePkgs.bcl-convert
                fastqc

                # for fake bclconvert
                fastq_generator
              ];
            };
          };
        }
      );
}
