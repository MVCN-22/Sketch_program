# Rebar Sketch Studio

Reinforcement for concrete structures designed in SOFiSTiK, from the required reinforcement to the detail drawings. Two programs run in the web browser, with nothing to install:

- **SOFiSTiK model** reads your SOFiSTiK model and BEMESS's required reinforcement. It proposes bars for every wall and slab (zones where more is needed, skew reinforcement following DIRE), checks the EN 1992-1-1 detailing rules, shows every bar in 3D, and exports sections for drawing and the bars to Tekla.
- **Simple sketch** (Rebar Drawing Studio) is for reinforcement drawings on A1 sheets:
  - sections, stirrups, rows of bars, labels such as "Y16/150 OS";
  - dimensions, notes and a title block;
  - export as PDF at true scale, SVG and DXF.

  It can import sections from the SOFiSTiK model, and keeps your detailing when you import again after the model changes.

> **Read [LIMITATIONS.md](LIMITATIONS.md) before using it for a design.** The program helps with layout and detailing. It does not replace the engineer's design and checks.

## Getting it

**Option 1: download.** Click the green **Code** button on this page → **Download ZIP**. Then:

1. In Windows Explorer, right-click the ZIP → **Extract All…** → Extract. *Do not open the files from inside the ZIP*: Windows then copies only the one file you click, and the links to the programs stop working.
2. Open the extracted folder and double-click `index.html`, so it opens in Chrome or Edge.
3. Pick **SOFiSTiK model** or **Drawing studio**. You can also open `sofistik-model.html` or `simple-sketch.html` directly.

**Option 2: use it online.** If the owner has switched on GitHub Pages, open the link from the repository description: `https://<owner>.github.io/<repository>/`. Clicking a `.html` file in the file list on github.com only shows its source code. The programs run from the Pages link, or from a download.

Either way, the programs run entirely in your browser. Your model, results and drawings are not sent anywhere. Work is kept in the browser, so save it as a project file to keep it. An internet connection is needed for the 3D view and custom sections, which load two libraries (three.js and jsts).

## Using it with SOFiSTiK

1. **Results from SOFiSTiK:**
   - Copy `rebar_export.dat` next to your project's `.dat`.
   - Add the line `#INCLUDE rebar_export.dat` at the end, after the design (BEMESS).
   - Every calculation then writes `<project>.rebar.txt` next to the `.cdb`. No Python is needed.
2. **Step 1 (Model):**
   - Open `sofistik-model.html`.
   - Drop in your `.dat` file and the files it includes.
   - Check the plan and the Notes tab.
   - Join areas that are one piece of concrete.
   - Draw cuts for the sections you want to detail.
3. **Step 2 (Required reinforcement):**
   - Open the `.rebar.txt`.
   - In the Results tab, tick the design cases that count, and mark the crack-width cases.
   - Choose the bar Ø, and review the zones.
4. **Step 3 (Design basis and details):** set the materials, the National Annex values, the bar lists and the covers.
5. **Step 4 (3D model and export):** check the bars and work through the check list. Then use:
   - "Export for drawing" (on step 1) for the drawing program;
   - the Tekla export, read by `tekla_rebars.py`.
6. **Drawings:**
   - Open `simple-sketch.html` → **Import from SOFiSTiK…** and pick the `.rsec.json` file.
   - Detail the sections.
   - Import again after the model changes: your changes are kept.

## Files

| File | What it is |
|---|---|
| `index.html` | Start page: choose one of the two programs |
| `sofistik-model.html` | The SOFiSTiK model program |
| `rebar_export.dat` | Block for your SOFiSTiK input that writes the results file |
| `Export results.cmd`, `export_results.py` | Older way to export results with Python (drop a `.cdb` on the `.cmd`) |
| `tekla_rebars.py` | Creates the bars in Tekla Structures (needs Python 3.8–3.12 and `pip install pythonnet`; see the top of the file) |
| `sofrebar.zip` | Python package for Grasshopper/Rhino (alternative route; unzip it where Rhino's Python finds it) |
| `simple-sketch.html` | The drawing program |
| `LIMITATIONS.md` | What the programs do not do, and what the engineer must still do |
| `.nojekyll` | An empty file that tells GitHub Pages to serve the files as they are |

## Requirements

- Chrome or Edge (current versions). Firefox mostly works; Safari is untested.
- SOFiSTiK with SOFiMSHC geometry and BEMESS for shell design, for the results export.
- Tekla Structures 2019 or later, only for the Tekla export.

## Status

This is a working tool under development. It has been tested on one project model. Results must be checked by the engineer responsible for the design. See [LIMITATIONS.md](LIMITATIONS.md).
