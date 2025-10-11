# zipviewer-tui

View and explore files in zip without unzipping
![alt text](md/image.png)
![](md/demo.gif)

## Installation

```bash
# Clone
git clone https://github.com/JBlitzar/zipviewer-tui.git && cd zipviewer-tui`
# Install dependencies
uv sync
# _replace `~/pkg_stuff` with somewhere else in your PATH_
ln main.py ~/pkg_stuff/zipviewer; chmod +x ~/pkg_stuff/zipviewer
```

## Usage

```bash
zipviewer <zip_file_path>
```
