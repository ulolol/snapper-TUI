# Snapper TUI

An interactive terminal user interface for managing Btrfs **snapper** snapshots with real-time feedback and direct command execution.

Browse, sort, restore, and delete snapshots all within your terminal. The TUI provides a responsive layout with live space usage tracking, animated loading indicators, and immediate operation feedback.

## Features

- **Browse Snapshots**: Sortable table with all metadata (number, type, date, user, description, cleanup policy, space usage)
- **Direct Execution**: Execute restore, delete, and status commands directly from the TUI with real-time feedback
- **Animated Loading**: Smooth braille spinner animation while fetching data from snapper
- **Auto-refresh**: Snapshots automatically refresh after successful deletion
- **Space Tracking**: Real-time disk usage display (requires Btrfs quota support)
- **Responsive Layout**: Optimized pane widths for better data visibility
- **Sort by Any Column**: Click table headers to toggle sorting
- **Detailed Preview**: View full snapshot metadata before executing commands
- **Multiple Exit Methods**: Press ESC or Ctrl+Q to quit

## Requirements

- **System**: Linux with Btrfs filesystem
- **Python**: 3.11 or newer
- **Textual**: 0.50 or newer
- **Snapper**: Installed and configured
- **Permissions**: Root access (via `sudo` or run as root)
- **Btrfs Quotas** (optional): For space usage data; enable with `sudo btrfs quota enable /`

## Installation

### Option 1: From Source (Recommended for Development)
```sh
git clone https://github.com/ulolol/snapper-TUI.git
cd snapper-TUI
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Option 2: Install from Package
```sh
pip install snapper-tui
```

### Option 3: Standalone Executable (Linux)
```sh
# Build the executable
pip install pyinstaller
pyinstaller \
  --onefile \
  --console \
  --collect-all textual \
  --add-data "snapper_tui:snapper_tui" \
  run_snapper_tui.py -n snapper-tui

# Run it (still requires snapper installed)
sudo dist/snapper-tui
```

## Usage

### Launch
```sh
sudo snapper-tui
```

### Navigation & Keybindings
- **R** - Refresh snapshot list
- **ESC** or **Ctrl+Q** - Quit application
- **Arrow Keys** - Navigate table rows
- **Click Headers** - Sort by column

### Operations
1. **Select a snapshot** by clicking on a row
2. **View details** in the right panel:
   - Full snapshot metadata
   - Config and subvolume info
   - Three action buttons below
3. **Click an action button**:
   - **Restore**: Rollback to this snapshot
   - **Delete**: Remove this snapshot
   - **Status**: Show file changes
4. **See the result** immediately in the action panel
5. **List auto-refreshes** after successful deletion

### Environment Variables
```sh
# Monitor a different mount point
SNAPPER_TUI_ROOT_PATH=/home snapper-tui

# Example: monitor /home filesystem
sudo env SNAPPER_TUI_ROOT_PATH=/home snapper-tui
```

## Project Structure

```
snapper-TUI/
├── .gitignore               # Excludes files from git tracking
├── pyproject.toml           # Package metadata and dependencies
├── README.md                # This file
├── run_snapper_tui.py       # PyInstaller entry point
├── snapper-tui.spec         # PyInstaller spec file for standalone executable
├── snapper_tui/
│   ├── __init__.py          # Package info
│   ├── __main__.py          # CLI entry point
│   ├── app.py               # Main Textual application
│   ├── data.py              # Snapper JSON parsing
│   ├── utils.py             # Formatting and disk utilities
│   └── styles.css           # Terminal UI styling
```

## Technical Details

### Modern Architecture
- **Textual 0.50+**: Uses modern `compose()` API for widget composition
- **Python 3.11+**: Native type hints (`list[T]`, `T | None`) throughout
- **Async/Await**: Non-blocking operations for smooth UX
- **Error Handling**: Graceful failures with user-friendly messages

### How It Works
1. **Load**: Parses `snapper --jsonout list` output
2. **Display**: Renders sortable table with all metadata
3. **Interact**: User selects snapshot and clicks action
4. **Execute**: Runs snapper command directly (not just display)
5. **Feedback**: Shows success/error with auto-refresh on success

### Space Usage Data
Requires Btrfs quotas to be enabled and rescanned:
```sh
# Enable quotas on root filesystem
sudo btrfs quota enable /

# Rescan quotas (takes time on large filesystems)
sudo btrfs quota rescan /

# Verify
sudo btrfs quota show /
```

First rescan can take 15-60+ seconds depending on filesystem size. Subsequent `snapper list` calls are faster.

## Troubleshooting

### "Unable to read snapshots" Error
```sh
# Verify snapper works
sudo snapper list

# Check quota status
sudo btrfs quota show /

# Check filesystem
sudo btrfs filesystem show /
```

### Space usage showing "n/a"
Btrfs quotas are not enabled or still rescanning. See [Space Usage Data](#space-usage-data) above.

### Slow loading (28+ seconds)
This is normal with Btrfs quotas enabled. The `snapper list` command calculates space for each snapshot. Performance improves after the initial quota rescan completes.

### "snapper-tui: command not found"
Install the package:
```sh
pip install -e .  # development mode
# or
pip install .     # regular installation
```

### Binary won't run
Ensure you have:
- Python 3.11+ installed
- Textual 0.50+ available
- Snapper command installed: `which snapper`
- Root privileges: `sudo`

## Development

### Run in Development Mode
```sh
pip install -e .
sudo snapper-tui
```

### Build Executable
```sh
pip install pyinstaller
python -m build  # creates dist/ with wheel and sdist
pyinstaller --onefile --add-data "snapper_tui:snapper_tui" run_snapper_tui.py
```

### Run Tests (if available)
```sh
pytest tests/
```

## Performance Notes

- **Initial Load**: 28-30 seconds typical with Btrfs quotas (quota calculation time)
- **Subsequent Loads**: 5-10 seconds after quota rescan completes
- **Delete Operation**: 1-2 seconds (plus auto-refresh)
- **Restore (Rollback)**: Varies; updates are deferred
- **Status Comparison**: Depends on snapshot size

## Compatibility

- **Linux**: Yes (Btrfs required)
- **macOS**: No (no Btrfs)
- **Windows**: No (no Btrfs)
- **WSL**: Possible if WSL filesystem is Btrfs

## Known Limitations

- Requires `snapper` system command (not bundled)
- Requires root/sudo access to execute commands
- Space data only available with Btrfs quotas enabled
- Responsive UI is terminal-dependent (works best in modern terminals)

## Future Enhancements

- Confirmation dialogs for destructive operations
- Snapshot caching for faster reloads
- Search/filter functionality
- Snapshot diff viewer
- Export snapshot list to JSON/CSV
- Unit tests and continuous integration

## Contributing

Found a bug? Have a feature request? [Open an issue](https://github.com/ulolol/snapper-TUI/issues) on GitHub!

## License

MIT © Snapper TUI Contributors

## References

- [Snapper Documentation](https://github.com/openSUSE/snapper)
- [Textual Documentation](https://textual.textualize.io/)
- [Btrfs Wiki](https://btrfs.readthedocs.io/)
