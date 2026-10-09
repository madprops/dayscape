{
  description = "Dayscape — a private, day-by-day vibe journal for spotting the patterns in your life";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: rec {
        dayscape = pkgs.callPackage ./nix/package.nix { };
        default = dayscape;
      });

      apps = forAllSystems (
        pkgs:
        let
          pkg = self.packages.${pkgs.stdenv.hostPlatform.system}.dayscape;
        in
        rec {
          dayscape = {
            type = "app";
            program = "${pkg}/bin/dayscape";
          };
          default = dayscape;
        }
      );

      devShells = forAllSystems (
        pkgs:
        let
          python = pkgs.python3.withPackages (ps: [
            ps.pyside6
            ps.pytest
          ]);
          plugins = "lib/qt-6/plugins";
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.qt6.qtwayland
              pkgs.qt6.qtsvg
              pkgs.ruff
            ];
            shellHook = ''
              export QT_PLUGIN_PATH="${pkgs.qt6.qtbase}/${plugins}:${pkgs.qt6.qtwayland}/${plugins}:${pkgs.qt6.qtsvg}/${plugins}''${QT_PLUGIN_PATH:+:$QT_PLUGIN_PATH}"
              export DAYSCAPE_FONT_DIR="${pkgs.inter}/share/fonts"
              export PYTHONPATH="$PWD''${PYTHONPATH:+:$PYTHONPATH}"
              echo "dayscape dev shell — run: python -m dayscape   (or --demo for sample data)"
            '';
          };
        }
      );
    };
}
