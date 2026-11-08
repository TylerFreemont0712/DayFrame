# Third-party components

The native desktop uses Python, PySide6-Essentials/Qt, Shiboken, QtAwesome, QtPy, keyring, cryptography and tzdata. The build uses PyInstaller and NSIS for the Windows installer. The app's generated DayFrame mark is in assets; UI glyphs come from the bundled QtAwesome sets.

Preserve dependency license notices when redistributing. The bundle includes distribution metadata/notices under _internal/*dist-info, QtAwesome's supplied font assets/notices, and the available Python license under _internal/licenses/python. Exact installed versions are recorded in requirements-windows.lock.txt.

The installer build also copies the selected NSIS compiler's unmodified COPYING notice into _internal/licenses/nsis/COPYING before creating the installer and its uninstall manifest.

Source/project references:

- [Python](https://www.python.org/)
- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [PySide source](https://code.qt.io/cgit/pyside/pyside-setup.git/)
- [Qt source](https://code.qt.io/)
- [QtAwesome and icon/font notices](https://github.com/spyder-ide/qtawesome)
- [QtPy](https://github.com/spyder-ide/qtpy)
- [keyring](https://github.com/jaraco/keyring)
- [cryptography](https://github.com/pyca/cryptography)
- [tzdata](https://github.com/python/tzdata)
- [PyInstaller license and bootloader exception](https://pyinstaller.org/en/stable/license.html)
- [NSIS license notices](https://nsis.sourceforge.io/License)

Several color schemes adapt published palettes; colors were adjusted where needed for contrast. These projects are MIT-licensed, and DayFrame includes only color values, not their code or assets:

- [Nord](https://www.nordtheme.com/) by Arctic Ice Studio and Sven Greb
- [Catppuccin](https://catppuccin.com/)
- [Dracula](https://draculatheme.com/)
- [Tokyo Night](https://github.com/tokyo-night/tokyo-night-vscode-theme)
- [One Dark](https://github.com/atom/atom/tree/master/packages/one-dark-syntax) from Atom
- [Monokai](https://monokai.pro/) palette by Wimer Hazenberg
- [Gruvbox](https://github.com/morhetz/gruvbox) by Pavel Pertsev
- [Solarized](https://ethanschoonover.com/solarized/) by Ethan Schoonover
- [Rosé Pine](https://rosepinetheme.com/)
- [Everforest](https://github.com/sainnhe/everforest) by sainnhe

Dependencies retain their own licenses. No public project license has been selected for the owner's DayFrame source.
