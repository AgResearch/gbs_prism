{
  description = "Flake for gbs_prism development";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    flake-utils.url = "github:numtide/flake-utils";
    bcl-convert = {
      url = github:AgResearch/bcl-convert.nix/main;
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

        in
          with pkgs;
          {
            devShells = {
              default = mkShell {
                buildInputs = [
                  snakemake
                  flakePkgs.bcl-convert
                ];
              };
            };
          }
      );
}
