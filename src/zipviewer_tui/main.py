#! /usr/bin/env uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "textual",
# ]
# ///
from datetime import datetime

from textual.app import App, ComposeResult
from textual.widgets import Tree, Static, Button
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.widgets import Footer
import zipfile
import os
import sys
import tty
import termios
import subprocess


class ZipTree:
    def __init__(self, path, include_metadata_files=False):
        self.path = path
        self.zipfile_inst = zipfile.ZipFile(path, "r")
        self.tree = Tree(os.path.basename(path))

        file_list = self.zipfile_inst.namelist()
        self.real_file_paths = []
        self._build_tree(file_list, include_metadata_files)

    def _build_tree(self, file_list, include_metadata_files):
        def is_metadata_file(filename):
            if (
                filename == "__MACOSX"
                or filename == ".DS_Store"
                or filename.startswith("._")
            ):
                return True
            return False

        nodes = {}
        for file_path in file_list:
            parts = file_path.split("/")
            current_node = self.tree.root
            for part in parts[:-1]:
                if not include_metadata_files and is_metadata_file(part):
                    break
                else:
                    if part not in nodes:
                        nodes[part] = current_node.add(part, data=file_path)
                    current_node = nodes[part]
            if not (not include_metadata_files and is_metadata_file(parts[-1])):
                if parts[-1]:
                    current_node.add_leaf(parts[-1], data=file_path)
                    self.real_file_paths.append(file_path)

    def get_file_info(self, file_path):
        try:
            info = self.zipfile_inst.getinfo(file_path)
            return {
                "filename": info.filename,
                "file_size": info.file_size,
                "compress_size": info.compress_size,
                "modified_time": datetime(*info.date_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        except KeyError:
            return None

    def get_contents(self, file_path, max_size=1 * 1024 * 1024 * 1024):  # 1GB limit
        try:
            info = self.zipfile_inst.getinfo(file_path)
            if info.file_size > max_size:
                with self.zipfile_inst.open(file_path) as file:
                    data = file.read(1024)  # Read first 1KB for preview
                return data

            with self.zipfile_inst.open(file_path) as file:
                return file.read()
        except KeyError:
            return None

    def extract_file(self, file_path):
        try:
            dirname, fname = os.path.split(self.path)
            out = self.zipfile_inst.extract(file_path, path=dirname)
            out_dirname, out_fname = os.path.split(out)
            os.system(f'open -a Finder "{out_dirname}"')

            return True
        except KeyError:
            return False

    def extract_directory(self, dir_path):
        try:
            dirname, _ = os.path.split(self.path)

            dir_path = dir_path.rstrip("/") + "/"

            for name in self.zipfile_inst.namelist():
                if name.startswith(dir_path):
                    self.zipfile_inst.extract(name, dirname)

            out_dirname = os.path.join(dirname, dir_path)
            os.system(f'open -a Finder "{out_dirname}"')

            return True
        except KeyError:
            return False

    def extract_file_or_directory(self, path):
        if path.endswith("/"):
            return self.extract_directory(path)
        else:
            return self.extract_file(path)


class FilePreview(Static):
    image_file_extensions = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff", "svg"]

    @staticmethod
    def _check_chafa():
        try:
            result = subprocess.run(
                ["which", "chafa"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    chafa_exists = _check_chafa.__func__()

    def update_preview_showimg(self, path, content, appInstance):
        if path:
            ext = path.split(".")[-1].lower()
            if ext in self.image_file_extensions and self.chafa_exists:
                tmp_path = f"/tmp/zipviewer_{os.getpid()}.{ext}"
                with open(tmp_path, "wb") as f:
                    f.write(content)

                with appInstance.suspend():
                    subprocess.run(["chafa", tmp_path])

                    os.remove(tmp_path)
                    print("\nPress any key to continue...")
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        sys.stdin.read(1)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                self.update(
                    f"[bold green]Displayed image using chafa:[/bold green] {path}"
                )
                return True
        return False

    def update_preview(self, path, content, appInstance):
        if path:
            ext = path.split(".")[-1].lower()
            if ext in self.image_file_extensions and self.chafa_exists:
                text = "[bold green]Image viewing supported! Press v to view...[/bold green]\n"
                text += "[bold yellow]Binary file[/bold yellow]\n"
                text += f"First 256 bytes (hex):\n{' '.join(content[:256].hex()[i : i + 2] for i in range(0, len(content[:256].hex()), 2))}"
                self.update(text)
                return
        if isinstance(content, bytes):
            try:
                text = content.decode("utf-8")
                self.update(text)
            except UnicodeDecodeError:
                text = "[bold yellow]Binary file[/bold yellow]\n"
                text += f"First 256 bytes (hex):\n{' '.join(content[:256].hex()[i : i + 2] for i in range(0, len(content[:256].hex()), 2))}"
                self.update(text)
        else:
            self.update("[no content]")


class ZipViewerApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        height: 100%;
    }
    
    #tree-container {
        width: 40%;
        border-right: solid $primary;
    }
    
    #preview-container {
        width: 60%;
        padding: 1 2;
        overflow-y: auto;
    }

    """
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(key="e", action="extract_file", description="Extract selected file"),
        Binding(
            key="v",
            action="view_image",
            description="View image file (if selected and supported)",
        ),
    ]

    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.ziptree = ZipTree(os.path.expanduser(self.path))
        self.ziptree_tree = self.ziptree.tree

    def compose(self) -> ComposeResult:
        self.ziptree_tree.root.expand()
        with Horizontal():
            with Vertical(id="tree-container"):
                yield self.ziptree_tree
            with Vertical(id="preview-container"):
                yield Button("Extract File")
                yield Static("[file-info]", id="file-info")
                yield FilePreview(id="file-preview")

        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        self._selected_node = node

        file_info_widget = self.query_one("#file-info", Static)

        def pretty_format_bytes(size):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} PB"

        if node.data:
            info = self.ziptree.get_file_info(node.data)
            if info:
                file_info_widget.update(
                    f"[b]Filename:[/b] {info['filename']}\n"
                    f"[b]File Size:[/b] {pretty_format_bytes(info['file_size'])}\n"
                    f"[b]Compressed Size:[/b] {pretty_format_bytes(info['compress_size'])}\n"
                    f"[b]Modified Time:[/b] {info['modified_time']}\n"
                )
            else:
                file_info_widget.update("[red]Error retrieving file info.[/red]")

        content = self.ziptree.get_contents(node.data)
        preview_widget = self.query_one("#file-preview", FilePreview)
        if content is not None:
            preview_widget.update_preview(node.data, content, self)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if hasattr(self, "_selected_node"):
            if self._selected_node.data:
                self.ziptree.extract_file_or_directory(self._selected_node.data)

    def action_extract_file(self) -> None:
        if hasattr(self, "_selected_node"):
            if self._selected_node.data:
                self.ziptree.extract_file_or_directory(self._selected_node.data)

    def action_view_image(self) -> None:
        if hasattr(self, "_selected_node"):
            if self._selected_node.data:
                content = self.ziptree.get_contents(self._selected_node.data)
                preview_widget = self.query_one("#file-preview", FilePreview)
                if content is not None:
                    if not preview_widget.update_preview_showimg(
                        self._selected_node.data, content, self
                    ):
                        self.bell()


def main():
    if len(sys.argv) != 2:
        print("Usage: zipviewer <zip_file_path>")
        sys.exit(1)

    zip_path = sys.argv[1]
    app = ZipViewerApp(zip_path)
    app.run()


if __name__ == "__main__":
    main()
