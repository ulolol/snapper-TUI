"""Terminal UI implementation for Snapper snapshots."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from snapper_tui.data import SnapperError, Snapshot, list_snapshots
from snapper_tui.utils import (
    flatten_user_data,
    free_space_for_path,
    human_readable_bytes,
)

ROOT_PATH = os.environ.get("SNAPPER_TUI_ROOT_PATH", "/")


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    label: str
    width: int | None
    accessor: Callable[[Snapshot], str]
    sort_key: str


COLUMN_SPECS: list[ColumnSpec] = [
    ColumnSpec("number", "#", 6, lambda s: str(s.number), "number"),
    ColumnSpec(
        "snapshot_type", "Type", 10, lambda s: s.snapshot_type or "", "snapshot_type"
    ),
    ColumnSpec(
        "pre_number",
        "Pre",
        6,
        lambda s: str(s.pre_number) if s.pre_number is not None else "",
        "pre_number",
    ),
    ColumnSpec(
        "post_number",
        "Post",
        6,
        lambda s: str(s.post_number) if s.post_number is not None else "",
        "post_number",
    ),
    ColumnSpec("date", "Date", 20, lambda s: s.date or "", "date"),
    ColumnSpec("user", "User", 10, lambda s: s.user or "", "user"),
    ColumnSpec("cleanup", "Cleanup", 12, lambda s: s.cleanup or "", "cleanup"),
    ColumnSpec(
        "description", "Description", 40, lambda s: s.description or "", "description"
    ),
    ColumnSpec(
        "used_space",
        "Size",
        12,
        lambda s: human_readable_bytes(s.used_space),
        "used_space",
    ),
    ColumnSpec(
        "userdata",
        "Userdata",
        20,
        lambda s: flatten_user_data(s.userdata),
        "userdata",
    ),
]


class SnapperApp(App):
    """Textual TUI for browsing and acting on snapper snapshots."""

    TITLE = "Snapper TUI"
    CSS_PATH = "styles.css"
    BINDINGS = [
        ("r", "refresh", "Refresh snapshots"),
        ("escape", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    # Spinner animation frames
    SPINNER_FRAMES = ["⠏", "⠛", "⠖", "⠒", "⠐", "⠐", "⠒", "⠖", "⠛"]

    def __init__(self) -> None:
        super().__init__()
        self.snapshots: list[Snapshot] = []
        self.row_snapshot: dict[str, Snapshot] = {}
        self.selected_snapshot: Snapshot | None = None
        self.sort_key: str = "number"
        self.sort_reverse: bool = False
        self.snapshot_table: DataTable | None = None
        self.details_panel: Static | None = None
        self.action_message: Static | None = None
        self.space_summary: Static | None = None
        self.restore_button: Button | None = None
        self.delete_button: Button | None = None
        self.status_button: Button | None = None
        self.loading: bool = False
        self.spinner_index: int = 0

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=False)

        with Horizontal():
            snapshot_table = DataTable(id="snapshot_table", zebra_stripes=True)
            snapshot_table.cursor_type = "row"
            for spec in COLUMN_SPECS:
                snapshot_table.add_column(spec.label, width=spec.width, key=spec.key)
            self.snapshot_table = snapshot_table
            yield snapshot_table

            with Vertical(id="action_panel"):
                yield Static(
                    "Select a snapshot to view details.",
                    id="snapshot_details",
                )

                restore_button = Button(
                    "Restore snapshot",
                    id="action_restore",
                    variant="success",
                    disabled=True,
                )
                delete_button = Button(
                    "Delete snapshot",
                    id="action_delete",
                    variant="warning",
                    disabled=True,
                )
                status_button = Button(
                    "Snapshot status",
                    id="action_status",
                    variant="primary",
                    disabled=True,
                )
                self.restore_button = restore_button
                self.delete_button = delete_button
                self.status_button = status_button

                with Horizontal(id="action_buttons"):
                    yield restore_button
                    yield delete_button
                    yield status_button

                yield Static(
                    "Choose an action to preview the snapper command.",
                    id="action_message",
                )

        yield Static("", id="space_summary")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount event to initialize data."""
        self.details_panel = self.query_one("#snapshot_details", Static)
        self.action_message = self.query_one("#action_message", Static)
        self.space_summary = self.query_one("#space_summary", Static)

        # Load snapshots asynchronously
        self.call_later(self._load_snapshots)

    def _load_snapshots(self) -> None:
        """Load snapshots asynchronously."""
        asyncio.create_task(self.refresh_snapshots())

    async def _animate_loading(self) -> None:
        """Animate the loading spinner while fetching data."""
        while self.loading:
            frame = self.SPINNER_FRAMES[self.spinner_index % len(self.SPINNER_FRAMES)]
            if self.space_summary:
                self.space_summary.update(
                    f"{frame} Fetching snapshots from snapper (may take 20-30s)..."
                )
            self.spinner_index += 1
            await asyncio.sleep(0.1)

    async def refresh_snapshots(self) -> None:
        """Refresh the snapshot list from snapper."""
        # Start loading state and animation
        self.loading = True
        self.spinner_index = 0

        # Show loading message in all panels
        if self.space_summary:
            self.space_summary.update("⏳ Fetching snapshots from snapper (may take 20-30s)...")
        if self.details_panel:
            self.details_panel.update(
                "[bold cyan]⏳ Loading snapshot metadata...[/bold cyan]\n\n"
                "This can take a while as snapper calculates quota data.\n"
                "Please wait..."
            )
        if self.action_message:
            self.action_message.update(
                "[bold yellow]⠏ Loading in progress...[/bold yellow]\n"
                "Querying snapper for snapshot information."
            )
        if self.restore_button and self.delete_button and self.status_button:
            self.restore_button.disabled = True
            self.delete_button.disabled = True
            self.status_button.disabled = True
        if self.snapshot_table:
            self.snapshot_table.clear()
        self.row_snapshot.clear()
        self.selected_snapshot = None
        self.sort_key = "number"
        self.sort_reverse = False

        # Start spinner animation in background
        animation_task = asyncio.create_task(self._animate_loading())

        try:
            snapshots = await asyncio.to_thread(list_snapshots)
        except SnapperError as exc:
            self.loading = False
            message = f"Unable to read snapshots: {exc}"
            if self.space_summary:
                self.space_summary.update(message)
            if self.details_panel:
                self.details_panel.update(
                    "Check that snapper can be run from this shell."
                )
            animation_task.cancel()
            return

        # Stop loading state
        self.loading = False
        animation_task.cancel()

        self.snapshots = snapshots
        self._update_table()
        self._update_summary()
        # Clear loading messages and show ready state
        if self.details_panel:
            self.details_panel.update("Select a snapshot to view details.")
        if self.action_message:
            self.action_message.update(
                "Choose an action to preview the snapper command."
            )
        if self.snapshot_table:
            self.set_focus(self.snapshot_table)

    def _update_table(self) -> None:
        """Update the snapshot table with current data."""
        if not self.snapshot_table:
            return
        self.snapshot_table.clear()
        self.row_snapshot.clear()
        sorted_snapshots = sorted(
            self.snapshots,
            key=lambda snap: self._value_for_sort(snap, self.sort_key),
            reverse=self.sort_reverse,
        )
        for snapshot in sorted_snapshots:
            row_key = f"{snapshot.config}:{snapshot.number}"
            self.row_snapshot[row_key] = snapshot
            cells = [spec.accessor(snapshot) for spec in COLUMN_SPECS]
            self.snapshot_table.add_row(*cells, key=row_key)

    def _value_for_sort(self, snapshot: Snapshot, sort_key: str) -> Any:
        """Get the sort value for a snapshot field."""
        if sort_key == "userdata":
            return flatten_user_data(snapshot.userdata)
        value = getattr(snapshot, sort_key, "")
        if value is None:
            return ""
        return value

    def _update_summary(self) -> None:
        """Update the space summary display."""
        if not self.space_summary:
            return
        total_used = sum((snap.used_space or 0) for snap in self.snapshots)
        free_space = free_space_for_path(ROOT_PATH)
        used_text = human_readable_bytes(total_used)
        free_text = human_readable_bytes(free_space)
        summary = (
            f"Snapshots: {len(self.snapshots)} | "
            f"Total used: {used_text} | "
            f"Free on {ROOT_PATH}: {free_text}"
        )
        self.space_summary.update(summary)

    def _refresh_details(self) -> None:
        """Refresh the details panel for the selected snapshot."""
        if not self.details_panel:
            return
        if not self.selected_snapshot:
            self.details_panel.update("Select a snapshot to view details.")
            if self.action_message:
                self.action_message.update(
                    "Choose an action to preview the snapper command."
                )
            return
        snap = self.selected_snapshot
        user_data = flatten_user_data(snap.userdata)
        detail_lines = [
            f"Config: {snap.config}  Subvolume: {snap.subvolume}",
            f"Number: {snap.number} ({snap.snapshot_type})",
            f"Description: {snap.description or '<no description>'}",
            f"User: {snap.user}  Cleanup: {snap.cleanup or '<none>'}",
            f"Pre #: {snap.pre_number or '-'}  Post #: {snap.post_number or '-'}",
            f"Default: {'yes' if snap.default else 'no'}  Active: {'yes' if snap.active else 'no'}",
            f"Used space: {human_readable_bytes(snap.used_space)}",
            f"Userdata: {user_data or '<none>'}",
        ]
        self.details_panel.update(dedent("\n".join(detail_lines)))
        if self.restore_button and self.delete_button and self.status_button:
            self.restore_button.disabled = False
            self.delete_button.disabled = False
            self.status_button.disabled = False
        if self.action_message:
            restore_cmd = f"sudo snapper rollback {snap.number}"
            delete_cmd = f"sudo snapper delete {snap.number}"
            status_base = (
                snap.pre_number
                if snap.pre_number is not None
                else max(0, snap.number - 1)
            )
            status_cmd = f"sudo snapper status {status_base}..{snap.number}"
            self.action_message.update(
                "\n".join(
                    [
                        f"Restore command: {restore_cmd}",
                        f"Delete command: {delete_cmd}",
                        f"Status command: {status_cmd}",
                        "Press a button to highlight the command above.",
                    ]
                )
            )

    async def on_data_table_header_selected(
        self, event: DataTable.HeaderSelected
    ) -> None:
        """Handle sorting when table header is clicked."""
        if event.column_key is None:
            return
        matching = next(
            (spec for spec in COLUMN_SPECS if spec.key == event.column_key), None
        )
        if not matching:
            return
        if self.sort_key == matching.sort_key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = matching.sort_key
            self.sort_reverse = False
        self._update_table()

    async def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        """Handle snapshot selection."""
        snapshot = self.row_snapshot.get(event.row_key)
        self.selected_snapshot = snapshot
        self._refresh_details()

    async def action_refresh(self) -> None:
        """Action to refresh snapshots."""
        await self.refresh_snapshots()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id not in {"action_restore", "action_delete", "action_status"}:
            return
        if not self.selected_snapshot or not self.action_message:
            return
        snap = self.selected_snapshot

        if event.button.id == "action_restore":
            await self._execute_restore(snap)
        elif event.button.id == "action_delete":
            await self._execute_delete(snap)
        else:
            await self._execute_status(snap)

    async def _execute_delete(self, snap: Snapshot) -> None:
        """Execute delete command for a snapshot."""
        if not self.action_message:
            return

        self.action_message.update(
            "[bold yellow]⏳ Executing delete...[/bold yellow]"
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["snapper", "delete", str(snap.number)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                self.action_message.update(
                    f"[bold green]✓ Snapshot {snap.number} deleted successfully![/bold green]\n\n"
                    f"Refreshing list..."
                )
                # Auto-refresh after a short delay
                await asyncio.sleep(1.0)
                await self.refresh_snapshots()
            else:
                self.action_message.update(
                    f"[bold red]✗ Delete failed:[/bold red]\n"
                    f"{result.stderr or result.stdout}"
                )
        except Exception as exc:
            self.action_message.update(
                f"[bold red]✗ Error: {exc}[/bold red]"
            )

    async def _execute_restore(self, snap: Snapshot) -> None:
        """Execute restore (rollback) command for a snapshot."""
        if not self.action_message:
            return

        self.action_message.update(
            "[bold yellow]⏳ Executing restore...[/bold yellow]\n"
            "This may take a while..."
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["snapper", "rollback", str(snap.number)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                self.action_message.update(
                    f"[bold green]✓ Rollback to snapshot {snap.number} complete![/bold green]\n\n"
                    f"Press 'R' to refresh or reboot to apply changes."
                )
            else:
                self.action_message.update(
                    f"[bold red]✗ Restore failed:[/bold red]\n"
                    f"{result.stderr or result.stdout}"
                )
        except Exception as exc:
            self.action_message.update(
                f"[bold red]✗ Error: {exc}[/bold red]"
            )

    async def _execute_status(self, snap: Snapshot) -> None:
        """Execute status command for a snapshot."""
        if not self.action_message:
            return

        self.action_message.update(
            "[bold cyan]⏳ Fetching status...[/bold cyan]"
        )

        try:
            start = (
                snap.pre_number
                if snap.pre_number is not None
                else max(0, snap.number - 1)
            )
            result = await asyncio.to_thread(
                subprocess.run,
                ["snapper", "status", f"{start}..{snap.number}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                # Show first 500 chars of output
                output = result.stdout[:500]
                self.action_message.update(
                    f"[bold cyan]Status output:[/bold cyan]\n{output}"
                )
            else:
                self.action_message.update(
                    f"[bold red]✗ Status failed:[/bold red]\n"
                    f"{result.stderr or result.stdout}"
                )
        except Exception as exc:
            self.action_message.update(
                f"[bold red]✗ Error: {exc}[/bold red]"
            )
