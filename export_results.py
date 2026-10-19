"""SOFiSTiK results for Rebar Sketch Studio: the required reinforcement of every shell element, read from the .cdb, written as
<model>.results.json next to it. Open that file on step 2 of the website ("Results").

    python export_results.py [model.cdb] [--case N]

Without a file, a window asks for one. SOFiSTiK must be installed on this PC (its CDB interface reads the file). The .cdb is
read from a temporary copy; nothing in it is changed, and nothing is sent anywhere.
"""
import os, sys, json, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sofrebar import cdb

FORMAT = "rebar-studio/results-1"


def r(v, n=1): return round(float(v), n)


def export(path, case=None, out=None):
    M = cdb.read(path, case)
    sars, els = {}, []
    for sar, A in sorted(M.areas.items()):
        sars[str(sar)] = {"t": r(A.t), "grp": A.grp, "x": [r(c, 5) for c in A.x], "y": [r(c, 5) for c in A.y], "z": [r(c, 5) for c in A.z],
                          "n": len(A.els), "max": [r(max(e.req[k] for e in A.els), 2) for k in range(4)]}
        for e in A.els:
            row = [e.nr, sar, r(e.a, 4)] + [r(v, 2) for v in e.req]
            for P in e.pts: row += [r(P[0]), r(P[1]), r(P[2])]
            els.append(row)
    data = {"format": FORMAT, "source": os.path.basename(path),
            "modified": datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds"),
            "created": datetime.datetime.now().isoformat(timespec="seconds"), "units": "mm, cm²/m",
            "layers": ["upper along local x", "upper along local y", "lower along local x", "lower along local y"], "axes": "local",
            "faces": "upper: the face against the local z axis (SOFiSTiK)",
            "groups": {str(g): P for g, P in sorted(M.para.items())},
            "case": case, "cases": M.cases, "has_results": M.has_results, "notes": M.notes,
            "sars": sars, "element": "number, SAR, area [m²], required upper along local x, upper along local y, lower along local x, lower along local y [cm²/m], corners x y z [mm]",
            "els": els}
    out = out or os.path.splitext(path)[0] + ".results.json"
    with open(out, "w", encoding="utf-8") as f: json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    return out, M


def ask():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        p = filedialog.askopenfilename(title="The SOFiSTiK database (.cdb) to export", filetypes=[("SOFiSTiK database", "*.cdb")])
        root.destroy()
        return p or None
    except Exception:
        return input("The .cdb file: ").strip().strip('"') or None


def main():
    ap = argparse.ArgumentParser(description="SOFiSTiK results (.cdb) for Rebar Sketch Studio")
    ap.add_argument("cdb", nargs="?", help="the .cdb file (asked for when left out)")
    ap.add_argument("--case", type=int, help="one design case (default: the largest of all)")
    ap.add_argument("--out", help="where to write (default: next to the .cdb, as <name>.results.json)")
    a = ap.parse_args()
    path = a.cdb or ask()
    if not path: print("No file chosen."); return 1
    if not path.lower().endswith(".cdb"): print("Not a .cdb file: %s" % path); return 1
    try:
        out, M = export(path, a.case, a.out)
    except Exception as e:
        print("Could not read %s:\n  %s" % (path, e)); return 1
    n = sum(len(A.els) for A in M.areas.values())
    print("Read %s: %d areas, %d elements; design cases: %s" % (os.path.basename(path), len(M.areas), n, ", ".join(map(str, M.cases)) or "none"))
    for note in M.notes: print("  note: " + note)
    print("Written: %s\nOpen it on step 2 of the website (Results > Open results)." % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
