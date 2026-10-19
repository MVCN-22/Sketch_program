# Rebar Sketch Studio: limitations for detailed design (Version R)

This program helps turn a SOFiSTiK design into a reinforcement layout and drawings. **It is not a design program, and its check is not a design check.** It takes the reinforcement SOFiSTiK (BEMESS) asks for, chooses bars to cover it, and checks some EN 1992-1-1 detailing rules. Everything below must be covered by the engineer's own calculations or by hand.

Status: the program has been tested on one real model (walls and slabs of a building). It has not been validated on bridges, large decks or other structure types. Compare its results with SOFiSTiK's own plots before relying on it for a new type of structure.

---

## 1. Reading the model (.dat)

- **Supported input:** SOFiSTiK geometry (SOFiMSHC: SPT, SLN, SAR, SARB, SLNB) with AQUA sections and materials, or a SAF file (.xlsx).
  - Models made only of FE elements (QUAD/NODE without structural areas) cannot be read.
- **What is used:** structural areas (SAR) and beams/columns (SLN with an AQUA section). Supports, loads, springs, couplings and construction stages are not read.
- **Steel beams** are left out. Beams with a section of unknown material are taken as concrete.
- **Silent risks**, each shown under step 1 → Notes:
  - Variables the reader cannot evaluate are read as **0**.
  - Points with REF (relative or projected coordinates) are read as plain x, y, z.
  - The thickness unit is guessed when the file does not state it.
  - The vertical direction comes from GDIR.

  Check that the plan on step 1 looks like the structure.
- **Materials:** only the **first** concrete (CONC) and the **first** steel (STEE) of the model are used, for the whole structure. A structure with several concrete classes (for example deck and substructure) is checked with one class. Set the class by hand where it differs, and check the other parts separately.
- **Areas:** curved and warped areas get bars that follow the surface, but zones cannot be drawn on them and they cannot be joined. Areas are joined only when the engineer joins them (step 1).

## 2. Results from SOFiSTiK

- **Shells only.** The results are BEMESS's required reinforcement of shell elements (records 260, per design case). **Not read:**
  - beam and column design (AQB): required areas of beams and columns must be typed on step 2;
  - shear reinforcement of shells (ASW);
  - punching.
- **One value per FE element.** It is not documented here whether SOFiSTiK stores centre or averaged values in that record. Peaks at supports, column heads and re-entrant corners depend on the mesh. The optional averaging width (step 2) smooths them. Its value is the engineer's choice and is printed on the check.
- **Design cases:** the program takes the largest value of the cases ticked as "counts". It cannot tell ULS, crack width, stresses or an envelope apart:
  - the engineer must tick the cases that belong to the design;
  - leave out envelope cases;
  - mark the crack-width cases.
- **Crack width:** only recognised where a crack-width case is marked and governs. There the bars keep BEMESS's diameter. The program does not compute crack widths itself, and a different Ø than BEMESS assumed invalidates BEMESS's crack design.
- **Prestressing:** BEMESS includes it in the required areas, but the program knows nothing about tendons. There is no space for ducts, no clash check, and no anchorage zones.
- **The older export** (results.json from Export results.cmd) holds the envelope only. Design cases cannot be chosen, and crack width cannot be recognised.

## 3. Skew reinforcement (new in Version R)

- **Supported:** an orthogonal mesh turned by an angle on each face. The angle follows BEMESS's DIRE (UPP for the upper face, LOW for the lower). It is taken into the groups automatically and can be changed per group or element on step 4. The check lists faces whose bars run at another angle than BEMESS designed for.
- **Not supported:**
  - two bar directions that are not at right angles to each other (a true skew net);
  - skew bars with the "global" naming (step 4). Use SOFiSTiK's naming.
  - directions that vary from element to element within a group. The bars follow the group's DIRE, and such elements are only listed.
- **Not proven on a real skew design:** the skew mapping has been tested with the test model turned to DIRE 30° and 60°, not on a real skew bridge deck.

## 4. Bar layout and detailing rules

- **Bar choice:** bars are chosen from the bar lists (diameters, spacings) to cover the required area, within the largest spacing of EN 1992-1-1 9.3.1.1 and 9.6.
- **Zones:** zones where more is needed are rectangles, or polygons along skew bars, around the FE elements that need more. They extend a_l = d past the area that needs them. The engineer should review zone extents and simplify them for construction.
- **Rules checked:**
  - required vs provided;
  - minimum reinforcement (9.2.1.1, 9.3.1.1, 9.6.2, 9.6.3);
  - largest spacing;
  - bar depth against BEMESS's assumed depth (GEOM);
  - beams and columns: minimum and maximum reinforcement, minimum links, link diameter and spacing;
  - bars outside the concrete, and covers that do not fit.
- **Not checked:**
  - clear spacing between bars across the whole 3D model: it is checked only in the sections drawn on step 5 (Details);
  - cover against exposure class and durability (the cover is taken as given);
  - fire, fatigue, accidental situations;
  - deflections;
  - bearing, splitting and local stresses;
  - corbels, half joints, construction joints;
  - concentrated loads.
- **National Annex:** the recommended values of EN 1992-1-1 are used. The Danish preset changes only γc and γs; its other values must be checked against the DK NA in force. EN 1992-1-1:2023 is not implemented.

## 5. Anchorage, laps and junctions: switched off

- **Field reinforcement only.** The bars are the field reinforcement: one bar per run, with no stock lengths and no laps. Bars end at the element edge, or at the far face of the element they meet. **Anchorage lengths, laps and the details where elements meet are not designed**, including:
  - corners with opening or closing moments (EN 1992-1-1 Annex J);
  - U-bars at junctions;
  - lap positions and staggering;
  - bond conditions.
- **Bar lengths** in schedules and in the Tekla export exclude anchorage and laps. They cannot be used for ordering as they are.
- **U-bars at free edges** get legs of 2h. Trimmer and diagonal bars at openings extend a_l = d past the corners, with no anchorage length.
- **Switching it back on:** the anchorage code is still in the program (`_dev\src\engine\features.js`), but it was set aside because its simplified junction rules could mislead.

## 6. Beams and columns

- **Required areas** are typed by hand (bottom, top in cm²; links in cm²/m). They are not read from SOFiSTiK.
- **Layouts:** simple only. Rectangular or circular sections, bars in one row per face, two-legged closed links.
- **Not covered:**
  - torsion reinforcement;
  - second-order effects;
  - the N_Ed term of the column minimum (0.10 N_Ed / f_yd: only 0.002 A_c is checked);
  - confinement;
  - seismic detailing.

## 7. Drawings (step 5 Details in the SOFiSTiK model, and Simple sketch)

- **Checks in the drawings:**
  - cover per bar: each bar's surface against its own c_nom (from the model for imported bars, else the view's or the document's);
  - clear spacing between cut bars: max(Ø, d_g + 5, 20) mm, EN 1992-1-1 8.2;
  - bars on top of each other, and bars outside the concrete.

  They see only what is drawn: bars running along a cut are one representative bar per layer, and dots against bar lines (a bar in a stirrup's bend) are not checked. Cover against the exposure class (c_min,dur), lap and anchorage spacing, and bundled bars are not checked.
- **CAD editing:** Move, Copy, Rotate, Mirror, Scale, Trim, Extend, Offset, Fillet, Break, Join, Erase and Line work on lines, bars and outlines in model mm. Arcs are drawn as short straight pieces. There are no arrays, blocks or layers of your own.

- **Manual drawing.** Drawings are made by hand, or started from sections imported from the model. An imported section shows:
  - the bars crossing the cut as dots;
  - one representative bar per layer for bars running along the cut, not every bar.
- **No bar marks or schedule:** there are no bar marks, shape codes or bar schedule in the drawing program. Labels are generated from the bars, and their text can be overridden by hand.
- **One-way link:** model → drawing. Changes in the drawing (moved or added bars) do not go back to the model, its 3D view, its schedule or the Tekla export.
- **Re-import:** after the model changes, imported items the engineer did not touch are updated, and the engineer's edits are kept. Check the import report and the items marked "Changed by you; the model now has …".
- **Export formats:** DXF is R12, without line weights, and its layers do not follow a company CAD standard.

## 8. Tekla export

Bars go to Tekla as polylines with a bending radius. They are not parametric rebar sets that follow model changes, so a model change means export and import again. The export has not been tested against every Tekla environment (grade, size and class names may need setting in `tekla_rebars.py`).

## 9. Software and quality assurance

- **Tests:** the program has automated tests (about 800 checks in the model program, 1,150 in the drawing program). They prove that the program behaves as intended and gives the same numbers as before. They are **not an independent verification** of the engineering. There is no validation report against hand calculations for a range of structures.
- **Browser and network:**
  - The program runs in the browser.
  - The 3D view and custom sections load two libraries (three.js, jsts) from the internet.
  - Work is kept in the browser and in project files: save the project file to keep it.
- **Performance:** not measured on large models. A bridge with 100,000 elements may be slow in the browser and when SOFiSTiK writes the results file.

---

## What the engineer must still do for a detailed design

1. Check that the model was read correctly (step 1, Notes; the plan; units).
2. Choose and mark the design cases (step 2, Results), and decide on an averaging width.
3. Design shear and punching, and beams and columns (AQB), outside this program.
4. Design and detail anchorage, laps, corners and junctions, and openings.
5. Check cover against exposure, crack widths, fatigue, fire and accidental situations where relevant.
6. Review the zones, and simplify them for construction.
7. Check the bar schedules and bar lengths (they exclude anchorage and laps) before ordering.
8. Work through every open item of the check, and record a reason for every accepted one.
9. Compare a few elements with SOFiSTiK's result plots, especially for skew or new types of structure.
