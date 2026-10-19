"""
Rebar Sketch Studio -> Tekla Structures: native, editable reinforcing bars.

Reads the file exported from Rebar Sketch Studio (SOFiSTiK model, step 4, Export: "Tekla rebars (.json)")
and creates the bars in the Tekla model that is open:

  - bars of one shape at a constant spacing become one RebarGroup (stretch it, change its spacing,
    or ungroup it in Tekla for local changes); all other bars become SingleRebars;
  - every bar lies on the exported centre line: the on-plane and from-plane cover are set to -diameter/2,
    because Tekla measures cover to the outer surface of the bar; bends are left to Tekla, with the bending
    radius from the export (inner radius, mandrel / 2);
  - each bar needs a concrete part as its father: an existing part found where the bars are, or a slab or
    wall panel created from the SOFiSTiK area (outline, openings and thickness).

Requirements
  - Tekla Structures running, with the model open (any version with the .NET Open API, 2019 or later)
  - Python 3.8 to 3.12, 64-bit, and pythonnet:   py -m pip install pythonnet

Use
  py tekla_rebars.py model.tekla.json                     create the bars (finds or creates the concrete)
  py tekla_rebars.py model.tekla.json --concrete find     only attach to concrete already in the model
  py tekla_rebars.py model.tekla.json --concrete create   always create the concrete panels from the areas
  py tekla_rebars.py model.tekla.json --concrete pick     pick one part in Tekla for all the bars
  py tekla_rebars.py model.tekla.json --singles           no groups: every bar a SingleRebar
  py tekla_rebars.py model.tekla.json --offset 1000 0 0   move everything (mm), to line up with the Tekla model
  py tekla_rebars.py --remove model.tekla-log.json        delete what an earlier run created
  py tekla_rebars.py model.tekla.json --dry-run           read the file and report, without Tekla

Grade, size names and classes differ between Tekla environments: see the options below (--grade, --size,
--class-*), or change the defaults in CONFIG.
"""
import argparse
import glob
import json
import math
import os
import sys
import time

CONFIG = {
    "grade": "B500B",            # steel grade as named in your environment
    "size": "{d}",               # the size name: "{d}" gives "12"; e.g. "{d}B500B" or "Ø{d}" in other environments
    "material": "{concrete}",    # concrete material for created panels ("{concrete}" = the class from the export)
    "name_prefix": "",           # put in front of every bar name
    "classes": {                 # Tekla class (colour) by kind of bar
        "mesh_0": 2, "mesh_1": 3, "zone": 6, "ubar": 7, "trim": 8, "diag": 9, "curved": 4,
    },
    "part_class": "8",           # class of created concrete panels
    "search": 60.0,              # how far (mm) outside a part's box a bar may lie and still be attached to it
}


# --------------------------------------------------------------------------- the export file
def read_export(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not str(data.get("format", "")).startswith("rebar-sketch-studio/tekla"):
        raise SystemExit(f"{path} is not a Tekla export of Rebar Sketch Studio")
    return data


def summary(data):
    sets = sum(len(L["sets"]) for L in data["layers"])
    grouped = sum(s["n"] for L in data["layers"] for s in L["sets"] if s["n"] > 1)
    bars = sum(s["n"] for L in data["layers"] for s in L["sets"])
    return (f"{data.get('source', '?')}: {len(data['parts'])} areas, {len(data['layers'])} layers, {bars} bars "
            f"({grouped} in {sum(1 for L in data['layers'] for s in L['sets'] if s['n'] > 1)} groups, "
            f"{bars - grouped} single), {sets} objects to create")


# --------------------------------------------------------------------------- Tekla Open API through pythonnet
def tekla_bin(hint=None):
    cands = [hint, os.environ.get("TEKLA_BIN")]
    for root in [r"C:\Program Files\Tekla Structures", r"C:\Program Files (x86)\Tekla Structures"]:
        for v in sorted(glob.glob(os.path.join(root, "*")), reverse=True):
            cands += [os.path.join(v, "bin"), os.path.join(v, "nt", "bin")]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "Tekla.Structures.Model.dll")):
            return c
    raise SystemExit("Tekla Structures was not found. Give its bin folder with --tekla "
                     "(the folder with Tekla.Structures.Model.dll).")


class Api:
    """the parts of the Open API used here"""

    def __init__(self, bin_dir):
        try:
            import clr  # pythonnet
        except ImportError:
            raise SystemExit("pythonnet is missing: py -m pip install pythonnet")
        sys.path.append(bin_dir)
        clr.AddReference("Tekla.Structures")
        clr.AddReference("Tekla.Structures.Model")
        import System
        from System.Collections import ArrayList
        import Tekla.Structures.Model as TSM
        import Tekla.Structures.Geometry3d as G3
        import Tekla.Structures.Model.UI as UI
        self.System, self.ArrayList, self.M, self.G, self.UI = System, ArrayList, TSM, G3, UI
        self.model = TSM.Model()
        if not self.model.GetConnectionStatus():
            raise SystemExit("No connection to Tekla Structures: start it and open the model first.")

    def point(self, p):
        return self.G.Point(float(p[0]), float(p[1]), float(p[2]))


# --------------------------------------------------------------------------- concrete
def real(o):
    """pythonnet 3 hands objects over as the type the method declares (ModelObject): get the actual one"""
    return getattr(o, "__implementation__", o) if o is not None else None


def unit(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / l for c in v]


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def mul(a, k):
    return [a[0] * k, a[1] * k, a[2] * k]


class Concrete:
    """finds or creates the father part of the bars"""

    def __init__(self, api, data, mode, log):
        self.api, self.data, self.mode, self.log = api, data, mode, log
        self.parts = {p["no"]: p for p in data["parts"]}
        self.created = {}         # area no -> created part
        self.found = {}           # cache of found parts by rounded point
        self.picked = None
        self.boxes = None
        self.warned = set()

    def _box_list(self):
        """the concrete parts of the model with their boxes (read once)"""
        if self.boxes is not None:
            return self.boxes
        api, M = self.api, self.api.M
        self.boxes = []
        objs = api.model.GetModelObjectSelector().GetAllObjects()
        while objs.MoveNext():
            o = real(objs.Current)
            if not isinstance(o, M.Part):
                continue
            ok, mt = o.GetReportProperty("MATERIAL_TYPE", "")
            if ok and str(mt).upper() != "CONCRETE":
                continue
            s = o.GetSolid()
            lo, hi = s.MinimumPoint, s.MaximumPoint
            self.boxes.append((o, (lo.X, lo.Y, lo.Z), (hi.X, hi.Y, hi.Z)))
        print(f"  {len(self.boxes)} concrete parts in the model")
        return self.boxes

    def find(self, P):
        key = tuple(round(c / 200.0) for c in P)
        if key in self.found:
            return self.found[key]
        e, best, bv = CONFIG["search"], None, None
        for o, lo, hi in self._box_list():
            if all(lo[k] - e <= P[k] <= hi[k] + e for k in range(3)):
                vol = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
                if bv is None or vol < bv:
                    best, bv = o, vol
        self.found[key] = best
        return best

    def create(self, no):
        if no in self.created:
            return self.created[no]
        api, M, p = self.api, self.api.M, self.parts.get(no)
        part = None
        if p and not p.get("curved"):
            part = M.ContourPlate()
            for q in p["contour"]:
                part.AddContourPoint(M.ContourPoint(api.point(q), None))
            part.Profile.ProfileString = f"PL{int(round(p['t']))}"
            part.Material.MaterialString = CONFIG["material"].format(concrete=self.data.get("concrete", "C35/45"))
            part.Position.Depth = M.Position.DepthEnum.MIDDLE
            part.Name = "SLAB" if p.get("horizontal") else "WALL"
            part.Class = CONFIG["part_class"]
            if part.Insert():
                self.log["parts"].append(str(part.Identifier.GUID))
                for h in p.get("holes", []):        # openings: cut with a thicker plate, then drop the cutting plate
                    cut = M.ContourPlate()
                    for q in h:
                        cut.AddContourPoint(M.ContourPoint(api.point(q), None))
                    cut.Profile.ProfileString = f"PL{int(round(p['t'])) + 100}"
                    cut.Material.MaterialString = part.Material.MaterialString
                    cut.Position.Depth = M.Position.DepthEnum.MIDDLE
                    cut.Class = M.BooleanPart.BooleanOperativeClassName
                    if cut.Insert():
                        b = M.BooleanPart()
                        b.Father = part
                        b.SetOperativePart(cut)
                        b.Insert()
                        cut.Delete()
            else:
                print(f"  ! the panel of SAR {no} could not be created")
                part = None
        self.created[no] = part
        return part

    def father(self, no, P):
        if self.mode == "pick":
            if self.picked is None:
                print("  pick the concrete part for the bars in Tekla ...")
                self.picked = real(self.api.UI.Picker().PickObject(self.api.UI.Picker.PickObjectEnum.PICK_ONE_PART,
                                                                   "Pick the concrete part for the bars"))
            return self.picked
        if self.mode in ("find", "auto"):
            f = self.find(P)
            if f is not None or self.mode == "find":
                return f
        f = self.create(no)
        if f is None:                               # a curved area: a part found there, or another created panel
            f = self.find(P) or next((q for q in self.created.values() if q is not None), None)
            if f is not None and no not in self.warned:
                self.warned.add(no)
                print(f"  ! SAR {no} is curved and gets no panel; its bars are attached to another part (change the father in Tekla)")
        return f


# --------------------------------------------------------------------------- bars
def class_of(L):
    c = CONFIG["classes"]
    if L.get("curved"):
        return c["curved"]
    if L["kind"] == "mesh":
        return c["mesh_1" if L.get("face") == 1 else "mesh_0"]
    return c.get(L["kind"], 1)


def setup(api, bar, L, father):
    """the properties a SingleRebar and a RebarGroup share"""
    M, d = api.M, float(L["d"])
    bar.Father = father
    bar.Size = CONFIG["size"].format(d=int(d) if d == int(d) else d)
    bar.Grade = CONFIG["grade"]
    bar.Name = (CONFIG["name_prefix"] + L["name"])[:60]
    bar.Class = int(class_of(L))
    if L.get("radius"):
        bar.RadiusValues.Add(float(L["radius"]))
    bar.OnPlaneOffsets.Add(-d / 2)                 # cover is measured to the bar surface: -d/2 puts the centre on the points
    bar.FromPlaneOffset = -d / 2
    cov = M.Reinforcement.RebarOffsetTypeEnum.OFFSET_TYPE_COVER_THICKNESS
    bar.StartPointOffsetType = cov
    bar.StartPointOffsetValue = 0.0
    bar.EndPointOffsetType = cov
    bar.EndPointOffsetValue = 0.0
    for hook in (bar.StartHook, bar.EndHook):
        hook.Shape = M.RebarHookData.RebarHookShapeEnum.NO_HOOK
    try:                                           # where the environment has this attribute
        bar.SetUserProperty("comment", L.get("comment", "")[:80])
    except Exception:
        pass


def polygon(api, pts, off):
    poly = api.M.Polygon()
    for q in pts:
        poly.Points.Add(api.point(add(q, off)))
    return poly


def create_bars(api, data, args, log):
    M = api.M
    conc = Concrete(api, data, args.concrete, log)
    off = list(args.offset)
    n_obj = n_bars = n_fail = 0
    no_father = 0
    t0 = time.time()
    for L in data["layers"]:
        for s in L["sets"]:
            pts, n, step = s["pts"], s["n"], s.get("step") or [0.0, 0.0, 0.0]
            mid = add(mul(add(pts[0], pts[-1]), 0.5), mul(step, (n - 1) / 2.0))
            father = conc.father(s.get("part", L["part"]), add(mid, off))
            LL = dict(L, radius=s["radius"]) if s.get("radius") else L     # U-bars: a radius that fits their web
            if father is None:
                no_father += n
                continue
            if n > 1 and not args.singles:
                g = M.RebarGroup()
                g.Polygons.Add(polygon(api, pts, off))
                setup(api, g, LL, father)
                sp = math.sqrt(sum(c * c for c in step))
                g.StartPoint = api.point(add(pts[0], off))
                # a hair short of (n - 1) spacings, so a target spacing gives exactly n bars
                g.EndPoint = api.point(add(add(pts[0], off), mul(step, (n - 1) * (1.0 - 1e-6))))
                g.SpacingType = M.BaseRebarGroup.RebarGroupSpacingTypeEnum.SPACING_TYPE_TARGET_SPACE
                g.Spacings.Add(sp)
                g.ExcludeType = M.BaseRebarGroup.ExcludeTypeEnum.EXCLUDE_TYPE_NONE
                for attr in ("StartFromPlaneOffset", "EndFromPlaneOffset"):   # newer versions: cover at the group's ends
                    if hasattr(g, attr):
                        setattr(g, attr, -float(L["d"]) / 2)
                ok = g.Insert()
                objs = [g] if ok else []
            else:
                objs = []
                ok = True
                for k in range(n):
                    b = M.SingleRebar()
                    b.Polygon = polygon(api, pts, add(off, mul(step, k)))
                    setup(api, b, LL, father)
                    if b.Insert():
                        objs.append(b)
                    else:
                        ok = False
            if ok:
                n_obj += len(objs)
                n_bars += n
            else:
                n_fail += n
            for o in objs:
                log["bars"].append(str(o.Identifier.GUID))
            if n_obj and n_obj % 200 == 0:
                print(f"  {n_obj} objects, {n_bars} bars ({time.time() - t0:.0f} s)")
    api.model.CommitChanges()
    print(f"Created {n_bars} bars in {n_obj} objects" + (f"; {n_fail} bars failed" if n_fail else "")
          + (f"; {no_father} bars had no concrete part to belong to" if no_father else "")
          + (f"; {sum(1 for v in conc.created.values() if v is not None)} concrete panels" if conc.created else "")
          + f" ({time.time() - t0:.0f} s).")


def remove(api, log_path):
    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)
    n = 0
    for g in log.get("bars", []) + log.get("parts", []):
        o = api.model.SelectModelObject(api.M.Identifier(api.System.Guid(g)))
        if o is not None and o.Delete():
            n += 1
    api.model.CommitChanges()
    print(f"Deleted {n} of {len(log.get('bars', [])) + len(log.get('parts', []))} objects of {log_path}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebar Sketch Studio -> Tekla Structures rebars")
    ap.add_argument("file", nargs="?", help="the .tekla.json exported from Rebar Sketch Studio")
    ap.add_argument("--concrete", choices=["auto", "find", "create", "pick"], default="auto",
                    help="auto: attach to concrete in the model, or create panels where there is none (default)")
    ap.add_argument("--singles", action="store_true", help="every bar a SingleRebar, no groups")
    ap.add_argument("--offset", nargs=3, type=float, default=[0.0, 0.0, 0.0], metavar=("DX", "DY", "DZ"),
                    help="move everything by this much (mm)")
    ap.add_argument("--grade", help=f"steel grade (default {CONFIG['grade']})")
    ap.add_argument("--size", help="size name, with {d} for the diameter (default \"{d}\")")
    ap.add_argument("--tekla", help="the Tekla bin folder, if it is not found")
    ap.add_argument("--remove", metavar="LOG", help="delete the objects an earlier run created (its log file)")
    ap.add_argument("--dry-run", action="store_true", help="only read the file and report")
    args = ap.parse_args(argv)
    if args.grade:
        CONFIG["grade"] = args.grade
    if args.size:
        CONFIG["size"] = args.size
    if args.remove:
        api = Api(tekla_bin(args.tekla))
        remove(api, args.remove)
        return
    if not args.file:
        ap.error("give the exported file")
    data = read_export(args.file)
    print(summary(data))
    if args.dry_run:
        return data
    api = Api(tekla_bin(args.tekla))
    wph = api.model.GetWorkPlaneHandler()
    old = wph.GetCurrentTransformationPlane()
    wph.SetCurrentTransformationPlane(api.M.TransformationPlane())    # global coordinates
    log = {"file": os.path.abspath(args.file), "parts": [], "bars": []}
    try:
        create_bars(api, data, args, log)
    finally:
        wph.SetCurrentTransformationPlane(old)
        lp = os.path.splitext(args.file)[0].replace(".tekla", "") + ".tekla-log.json"
        with open(lp, "w", encoding="utf-8") as f:
            json.dump(log, f)
        print(f"Log of what was created: {lp} (py tekla_rebars.py --remove \"{lp}\" deletes it again)")


if __name__ == "__main__":
    main()
