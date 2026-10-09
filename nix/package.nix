{
  lib,
  python3Packages,
  qt6,
  inter,
  makeDesktopItem,
  copyDesktopItems,
}:

python3Packages.buildPythonApplication {
  pname = "dayscape";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSource ../.;

  build-system = [ python3Packages.setuptools ];
  dependencies = [ python3Packages.pyside6 ];

  nativeBuildInputs = [
    qt6.wrapQtAppsHook
    copyDesktopItems
  ];
  buildInputs = [
    qt6.qtbase
    qt6.qtwayland
    qt6.qtsvg
  ];

  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  pythonImportsCheck = [ "dayscape" ];

  # nixpkgs' PySide6 does not always ship dist-info metadata the checker recognises.
  dontCheckRuntimeDeps = true;

  # Let the python wrapper carry the Qt plugin paths instead of double-wrapping.
  dontWrapQtApps = true;
  preFixup = ''
    makeWrapperArgs+=(
      "''${qtWrapperArgs[@]}"
      --set-default DAYSCAPE_FONT_DIR "${inter}/share/fonts"
    )
  '';

  postInstall = ''
    install -Dm644 dayscape/assets/dayscape.svg \
      $out/share/icons/hicolor/scalable/apps/dayscape.svg
  '';

  desktopItems = [
    (makeDesktopItem {
      name = "dayscape";
      exec = "dayscape";
      icon = "dayscape";
      desktopName = "Dayscape";
      genericName = "Vibe Journal";
      comment = "Rate and note each day, then see the patterns";
      categories = [
        "Office"
        "Utility"
      ];
      startupWMClass = "dayscape";
    })
  ];

  meta = {
    description = "A private, day-by-day vibe journal with heatmaps and trend insights";
    mainProgram = "dayscape";
    platforms = lib.platforms.linux;
  };
}
