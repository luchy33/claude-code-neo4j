"""Generate the AS-IS and TO-BE BPMN 2.0 diagrams for Ekte Mat Online.

Purpose (INFO212):
  * Describe both processes as data (pools, lanes, nodes, flows), with a source
    reference stored as <bpmn:documentation> on every element.
  * Lay the elements out on a grid and write valid BPMN 2.0 XML incl. diagram
    interchange (DI) so it opens in Camunda Modeler / bpmn.io.
  * Check layout (no flow line crosses another element), cross-check every
    story ID against EkteMat_backlog_v1.xlsx and verify every quote in the
    problem table verbatim against its source file.
  * Write the problem-to-story mapping table (Markdown).

Usage: python -I 02_bpmn_build_2026-10-22.py <repo_root_copy> <out_dir>
Rendering to SVG/PNG and bpmnlint are run separately (see mapping document).
"""
import csv, re, sys
from pathlib import Path
from xml.sax.saxutils import escape
import openpyxl

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
DATE = "2026-10-22"
SRC = {
 "ASIS": "02_Analysis_and_models/02_process_as-is-order-handling_2026-08-15.md",
 "OWN": "01_Requirements/sources/01_interview_owner_2026-08-14.txt",
 "EVC": "01_Requirements/sources/01_interview_event-coordinator_2026-08-15.txt",
 "CHF": "01_Requirements/sources/01_interview_head-chef_2026-08-15.txt",
 "CORP": "01_Requirements/sources/01_interview_corporate-customer_2026-08-19.txt",
 "ITL": "03_Architecture/03_landscape_current-it_2026-10-20.txt",
 "CSV": "04_Data/04_dataset_customer-emails_2026-10-20.csv",
 "BL": "01_Requirements/EkteMat_backlog_v1.xlsx",
}
norm = lambda s: re.sub(r"\s+", " ", s).strip()
TEXT = {k: norm((REPO / SRC[k]).read_text(encoding="utf-8")) for k in ("ASIS","OWN","EVC","CHF","CORP","ITL")}
EMAIL = {r["email_id"]: norm(r["body"]) for r in csv.DictReader(open(REPO / SRC["CSV"], encoding="utf-8"))}
ws = openpyxl.load_workbook(REPO / SRC["BL"], read_only=True)["User stories"]
STORIES = {r[0]: r[3] for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}
errors = []

# ----------------------------------------------------------------- geometry
COLW, RH, X_CONTENT = 170, 120, 165       # column width, row height, x of col 0 centre
SIZE = {"task": (134, 92), "event": (36, 36), "gateway": (50, 50)}
KIND = {"startEvent":"event","endEvent":"event","intermediateCatchEvent":"event",
        "exclusiveGateway":"gateway","eventBasedGateway":"gateway"}

class Diagram:
    def __init__(self, name, ncols):
        self.name, self.ncols = name, ncols
        self.pools, self.nodes, self.seq, self.msg, self.ann = [], {}, [], [], []
        self.y = 90
        self.width = X_CONTENT + ncols * COLW
    def pool(self, pid, name, lanes, process=True, x=0, w=None, collapsed=False, y=None):
        """lanes: list of (lane_id, lane_name, [row keys top->bottom]); lane_id None = pool without lanes."""
        p = {"id": pid, "name": name, "lanes": [], "process": process, "collapsed": collapsed,
             "x": x, "w": w or self.width}
        p["y"] = self.y if y is None else y
        yy = p["y"]
        if collapsed:
            p["h"] = 60
        else:
            for lid, lname, rows in lanes:
                p["lanes"].append({"id": lid, "name": lname, "y": yy, "h": len(rows) * RH, "rows": rows, "nodes": []})
                yy += len(rows) * RH
            p["h"] = yy - p["y"]
        if y is None: self.y = p["y"] + p["h"] + 40
        self.pools.append(p); return p
    def lane(self, lid):
        for p in self.pools:
            for l in p["lanes"]:
                if l["id"] == lid: return p, l
        raise KeyError(lid)
    def node(self, nid, typ, name, lane, col, row="M", doc="", defn=None, color=None):
        p, l = self.lane(lane)
        w, h = SIZE[KIND.get(typ, "task")]
        cx = X_CONTENT + col * COLW
        cy = l["y"] + l["rows"].index(row) * RH + RH / 2
        self.nodes[nid] = dict(id=nid, typ=typ, name=name, pool=p["id"], lane=lane, col=col,
            x=cx - w/2, y=cy - h/2, w=w, h=h, cx=cx, cy=cy, doc=doc, defn=defn, color=color)
        l["nodes"].append(nid)
    def flow(self, s, t, name="", style=None): self.seq.append((s, t, name, style))
    def message(self, s, t, name="", sdx=0, tdx=0): self.msg.append((s, t, name, sdx, tdx))
    def note(self, aid, text, x, y, w=250, h=64, to=None): self.ann.append((aid, text, x, y, w, h, to))

def box(d, ref):
    if ref in d.nodes: n = d.nodes[ref]; return n["x"], n["y"], n["w"], n["h"]
    p = next(p for p in d.pools if p["id"] == ref); return p["x"], p["y"], p["w"], p["h"]

def route_seq(d, s, t, style):
    a, b = d.nodes[s], d.nodes[t]
    ag, bg = a["typ"].endswith("Gateway"), b["typ"].endswith("Gateway")
    if abs(a["cy"] - b["cy"]) < 1:
        return [(a["x"] + a["w"], a["cy"]), (b["x"], b["cy"])]
    down = b["cy"] > a["cy"]
    if abs(a["cx"] - b["cx"]) < 1:
        return [(a["cx"], a["y"] + a["h"] if down else a["y"]), (b["cx"], b["y"] if down else b["y"] + b["h"])]
    if ag and style != "right":
        return [(a["cx"], a["y"] + a["h"] if down else a["y"]), (a["cx"], b["cy"]), (b["x"], b["cy"])]
    if bg:
        return [(a["x"] + a["w"], a["cy"]), (b["cx"], a["cy"]), (b["cx"], b["y"] if down else b["y"] + b["h"])]
    mx = b["cx"] - COLW / 2
    return [(a["x"] + a["w"], a["cy"]), (mx, a["cy"]), (mx, b["cy"]), (b["x"], b["cy"])]

def pool_of(d, ref):
    pid = d.nodes[ref]["pool"] if ref in d.nodes else ref
    return next(p for p in d.pools if p["id"] == pid)

def route_msg(d, s, t, sdx, tdx):
    sx_, sy_, sw, sh = box(d, s); tx_, ty_, tw, th = box(d, t)
    base_s = d.nodes[s]["cx"] if s in d.nodes else d.nodes[t]["cx"]
    base_t = d.nodes[t]["cx"] if t in d.nodes else d.nodes[s]["cx"]
    sx, tx = base_s + sdx, base_t + tdx
    up = ty_ < sy_
    ps, pt = pool_of(d, s), pool_of(d, t)
    gap = (pt["y"] + pt["h"] + ps["y"]) / 2 if up else (ps["y"] + ps["h"] + pt["y"]) / 2
    y1 = sy_ if up else sy_ + sh
    y2 = ty_ + th if up else ty_
    if abs(sx - tx) < 1: return [(sx, y1), (tx, y2)]
    return [(sx, y1), (sx, gap), (tx, gap), (tx, y2)]

def seg_hits(p, q, n, pad=3):
    x0, y0, x1, y1 = n["x"] + pad, n["y"] + pad, n["x"] + n["w"] - pad, n["y"] + n["h"] - pad
    if abs(p[0] - q[0]) < 1:   # vertical
        lo, hi = sorted((p[1], q[1])); return x0 < p[0] < x1 and lo < y1 and hi > y0
    lo, hi = sorted((p[0], q[0])); return y0 < p[1] < y1 and lo < x1 and hi > x0

def check_layout(d, edges):
    for eid, s, t, pts in edges:
        for n in d.nodes.values():
            if n["id"] in (s, t): continue
            for p, q in zip(pts, pts[1:]):
                if seg_hits(p, q, n): errors.append(f"{d.name}: {eid} ({s}->{t}) crosses {n['id']}")
    ids = list(d.nodes.values())
    for i, a in enumerate(ids):
        for b in ids[i+1:]:
            if a["x"] < b["x"]+b["w"] and b["x"] < a["x"]+a["w"] and a["y"] < b["y"]+b["h"] and b["y"] < a["y"]+a["h"]:
                errors.append(f"{d.name}: {a['id']} overlaps {b['id']}")

LABELS = []
def check_extra(d, edges):
    """Annotations and explicit labels must not be crossed by flows or overlap nodes."""
    boxes = [(aid, dict(id=aid, x=x, y=y, w=w, h=h)) for aid, t_, x, y, w, h, to in d.ann]
    boxes += [(f"label:{el}", dict(id=el, x=b[0], y=b[1], w=b[2], h=b[3])) for el, b in LABELS]
    for name, bx in boxes:
        for eid, s, t, pts in edges:
            if bx["id"] in (eid, s, t): continue
            for p, q in zip(pts, pts[1:]):
                if seg_hits(p, q, bx, pad=1): errors.append(f"{d.name}: {eid} crosses {name}")
        for n in d.nodes.values():
            if n["id"] == bx["id"]: continue
            if bx["x"] < n["x"]+n["w"] and n["x"] < bx["x"]+bx["w"] and bx["y"] < n["y"]+n["h"] and n["y"] < bx["y"]+bx["h"]:
                errors.append(f"{d.name}: {name} overlaps {n['id']}")

def stories_in(d):
    return sorted({m for n in d.nodes.values() for m in re.findall(r"US-\d\d", n["name"])})

# ------------------------------------------------------------------- writer
DEF = {"message": "<bpmn:messageEventDefinition id=\"{id}_def\" />", "timer": "<bpmn:timerEventDefinition id=\"{id}_def\" />"}
RED = ("#C00000", "#FFD7D7"); BLUE = ("#1F4E78", "#DDEBF7")

def write_bpmn(d, path):
    edges, out = [], []
    A = out.append
    A('<?xml version="1.0" encoding="UTF-8"?>')
    A('<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
      'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
      'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" xmlns:bioc="http://bpmn.io/schema/bpmn/biocolor/1.0" '
      'xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0" '
      f'id="Defs_{d.name}" targetNamespace="http://ektemat.example/bpmn" exporter="EkteMat INFO212 generator" exporterVersion="1.0">')
    A(f'<bpmn:collaboration id="Collab_{d.name}">')
    for p in d.pools:
        pr = f' processRef="Proc_{p["id"]}"' if p["process"] else ""
        A(f'<bpmn:participant id="{p["id"]}" name="{escape(p["name"])}"{pr} />')
    for i, (s, t, name, sdx, tdx) in enumerate(d.msg, 1):
        A(f'<bpmn:messageFlow id="Msg_{i}" name="{escape(name)}" sourceRef="{s}" targetRef="{t}" />')
        edges.append((f"Msg_{i}", s, t, route_msg(d, s, t, sdx, tdx)))
    for aid, text, *_ in d.ann:
        A(f'<bpmn:textAnnotation id="{aid}"><bpmn:text>{escape(text)}</bpmn:text></bpmn:textAnnotation>')
    for aid, text, x, y, w, h, to in d.ann:
        if to: A(f'<bpmn:association id="{aid}_assoc" sourceRef="{aid}" targetRef="{to}" />')
    A('</bpmn:collaboration>')
    seq_ids = {}
    for i, (s, t, name, style) in enumerate(d.seq, 1): seq_ids[(s, t)] = f"Flow_{d.name}_{i}"
    for p in d.pools:
        if not p["process"]: continue
        A(f'<bpmn:process id="Proc_{p["id"]}" isExecutable="false">')
        if p["lanes"][0]["id"] and len(p["lanes"]) > 0 and p["lanes"][0]["name"]:
            A(f'<bpmn:laneSet id="LS_{p["id"]}">')
            for l in p["lanes"]:
                A(f'<bpmn:lane id="{l["id"]}" name="{escape(l["name"])}">' + "".join(f"<bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>" for n in l["nodes"]) + "</bpmn:lane>")
            A('</bpmn:laneSet>')
        for n in d.nodes.values():
            if n["pool"] != p["id"]: continue
            inc = "".join(f"<bpmn:incoming>{seq_ids[(s,t)]}</bpmn:incoming>" for (s, t, *_ ) in d.seq if t == n["id"])
            outg = "".join(f"<bpmn:outgoing>{seq_ids[(s,t)]}</bpmn:outgoing>" for (s, t, *_ ) in d.seq if s == n["id"])
            doc = f"<bpmn:documentation>{escape(n['doc'])}</bpmn:documentation>" if n["doc"] else ""
            dfn = DEF[n["defn"]].format(id=n["id"]) if n["defn"] else ""
            A(f'<bpmn:{n["typ"]} id="{n["id"]}" name="{escape(n["name"])}">{doc}{inc}{outg}{dfn}</bpmn:{n["typ"]}>')
        for (s, t, name, style) in d.seq:
            if d.nodes[s]["pool"] != p["id"]: continue
            if d.nodes[t]["pool"] != p["id"]: errors.append(f"sequence flow across pools {s}->{t}")
            A(f'<bpmn:sequenceFlow id="{seq_ids[(s,t)]}" name="{escape(name)}" sourceRef="{s}" targetRef="{t}" />')
            edges.append((seq_ids[(s, t)], s, t, route_seq(d, s, t, style)))
        A('</bpmn:process>')
    A(f'<bpmndi:BPMNDiagram id="Dia_{d.name}"><bpmndi:BPMNPlane id="Plane_{d.name}" bpmnElement="Collab_{d.name}">')
    def shape(el, x, y, w, h, extra="", color=None, label=None):
        c = f' bioc:stroke="{color[0]}" bioc:fill="{color[1]}" color:border-color="{color[0]}" color:background-color="{color[1]}"' if color else ""
        lb = f'<bpmndi:BPMNLabel><dc:Bounds x="{label[0]:.0f}" y="{label[1]:.0f}" width="{label[2]:.0f}" height="{label[3]:.0f}" /></bpmndi:BPMNLabel>' if label else ""
        A(f'<bpmndi:BPMNShape id="{el}_di" bpmnElement="{el}"{extra}{c}><dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" />{lb}</bpmndi:BPMNShape>')
    def node_label(n):
        if n["typ"] == "task" or not n["name"]: return None
        lw = 100 if n["typ"].endswith("Gateway") else 96
        above = False
        for eid, s_, t_, pts in edges:
            if eid.startswith("Msg") and t_ == n["id"] and abs(pts[-1][1] - (n["y"] + n["h"])) < 1: above = True
            if eid.startswith("Flow") and s_ == n["id"] and abs(pts[0][1] - (n["y"] + n["h"])) < 1: above = True
        y = n["y"] - 36 if above else n["y"] + n["h"] + 5
        return (n["cx"] - lw / 2, y, lw, 30)
    LABELS.clear()
    for p in d.pools:
        shape(p["id"], p["x"], p["y"], p["w"], p["h"], ' isHorizontal="true"')
        for l in p["lanes"]:
            if l["name"]: shape(l["id"], p["x"] + 30, l["y"], p["w"] - 30, l["h"], ' isHorizontal="true"')
    for n in d.nodes.values():
        lab = node_label(n)
        if lab: LABELS.append((n["id"], lab))
        shape(n["id"], n["x"], n["y"], n["w"], n["h"], ' isMarkerVisible="true"' if n["typ"] == "exclusiveGateway" else "", n["color"], lab)
    for aid, text, x, y, w, h, to in d.ann:
        shape(aid, x, y, w, h)
    names = {f"Flow_{d.name}_{i}": (x[2], None) for i, x in enumerate(d.seq, 1)}
    names.update({f"Msg_{i}": (x[2], (x[3], x[4])) for i, x in enumerate(d.msg, 1)})
    for eid, s, t, pts in edges:
        nm, off = names[eid]; lb = ""
        if nm:
            p0, p1 = pts[0], pts[1]
            if eid.startswith("Flow"):
                if abs(p0[1] - p1[1]) < 1: lx, ly = p0[0] + 8, p0[1] - 22
                elif p1[1] < p0[1]: lx, ly = p0[0] + 6, p0[1] - 32
                else: lx, ly = p0[0] + 6, p0[1] + 6
                lb = (lx, ly, 56, 16)
            else:
                ps, pt = pool_of(d, s), pool_of(d, t)
                upper, lower = (pt, ps) if pt["y"] < ps["y"] else (ps, pt)
                gy = (upper["y"] + upper["h"] + lower["y"]) / 2
                lw = 7 * len(nm) + 6
                lx = p0[0] + 6 if off[0] >= 0 else p0[0] - 6 - lw
                bent = abs(pts[0][0] - pts[-1][0]) > 1
                ly = (gy + 4 if ps is lower else gy - 38) if bent else gy - 18
                lb = (lx, ly, lw, 16)
            if lb:
                LABELS.append((eid, lb))
                lb = f'<bpmndi:BPMNLabel><dc:Bounds x="{lb[0]:.0f}" y="{lb[1]:.0f}" width="{lb[2]:.0f}" height="{lb[3]:.0f}" /></bpmndi:BPMNLabel>'
        A(f'<bpmndi:BPMNEdge id="{eid}_di" bpmnElement="{eid}">' + "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}" />' for x, y in pts) + lb + "</bpmndi:BPMNEdge>")
    for aid, text, x, y, w, h, to in d.ann:
        if to:
            n = d.nodes[to]
            ty = n["y"] if y < n["y"] else n["y"] + n["h"]
            sy = y + h if y < n["y"] else y
            A(f'<bpmndi:BPMNEdge id="{aid}_assoc_di" bpmnElement="{aid}_assoc"><di:waypoint x="{n["cx"]:.0f}" y="{sy:.0f}" /><di:waypoint x="{n["cx"]:.0f}" y="{ty:.0f}" /></bpmndi:BPMNEdge>')
    A('</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn:definitions>')
    check_layout(d, edges)
    check_extra(d, edges)
    path.write_text("\n".join(out), encoding="utf-8")

def src(*refs): return "Source: " + "; ".join(refs)
AS, EV, OW, CH, CO = (Path(SRC[k]).name for k in ("ASIS","EVC","OWN","CHF","CORP"))
CSVN, ITN = Path(SRC["CSV"]).name, Path(SRC["ITL"]).name

# =================================================================== AS-IS
a = Diagram("asis", 23)
a.pool("P_Customer", "Customer", [("L_C", "", ["U", "M"])])
a.pool("P_EkteMat", "Ekte Mat AS", [("L_Coord", "Event coordinator", ["U", "M"]), ("L_Kitchen", "Kitchen", ["M"]),
                                    ("L_Driver", "Driver", ["M"]), ("L_Owner", "Owner", ["M"])])
N = a.node
N("c_start","startEvent","Catering need arises","L_C",0,doc=src(f"{AS} step 1 (trigger INFERRED)"))
N("c_send","task","P1 · Send request by e-mail, phone or web form","L_C",1,doc=src(f"{AS} step 1", f"{ITN} 'Website'"),color=RED)
N("c_quote","intermediateCatchEvent","Quote received","L_C",6,defn="message",doc=src(f"{AS} step 4"))
N("c_gw","exclusiveGateway","Accept quote?","L_C",7,doc=src(f"{AS} step 5"))
N("c_acc","task","P5 · Accept quote by e-mail (no confirmation sent)","L_C",8,doc=src(f"{AS} step 5", f"{CSVN} E011"),color=RED)
N("c_dec","task","Decline quote","L_C",9,"U",doc=src(f"{AS} step 5 ('If the customer accepts' - decline branch INFERRED)"))
N("c_enddec","endEvent","Not booked","L_C",10,"U",doc=src("INFERRED"))
N("c_gwW","exclusiveGateway","Wedding booking?","L_C",11,doc=src(f"{AS} step 6"))
N("c_pay","task","Pay deposit by Vipps","L_C",12,"U",doc=src(f"{AS} step 6"))
N("c_mW","exclusiveGateway","","L_C",13,doc="Merge gateway")
N("c_gwC","exclusiveGateway","Changes needed?","L_C",15,doc=src(f"{AS} step 8"))
N("c_chg","task","P9 · Report changes by phone or e-mail","L_C",16,"U",doc=src(f"{AS} step 8", f"{CSVN} E003"),color=RED)
N("c_mC","exclusiveGateway","","L_C",17,doc="Merge gateway")
N("c_conf","task","Confirm final guest numbers by phone","L_C",18,doc=src(f"{AS} step 9"))
N("c_food","intermediateCatchEvent","Food delivered","L_C",20,defn="message",doc=src(f"{AS} step 10"))
N("c_payinv","task","Pay invoice or Vipps request","L_C",21,doc=src(f"{AS} step 11"))
N("c_end","endEvent","Order completed","L_C",22,doc=src(f"{AS} step 11"))

N("e_start","startEvent","Request received","L_Coord",1,defn="message",doc=src(f"{AS} step 1-2"))
N("e_read","task","P2 · Read request (1-2 working days, up to 7 in peak season)","L_Coord",2,doc=src(f"{AS} step 2", f"{EV} Q2"),color=RED)
N("e_cap","task","P3 · Check capacity in Google Calendar (gut feeling)","L_Coord",3,doc=src(f"{AS} step 3", f"{EV} Q4"),color=RED)
N("e_gw1","exclusiveGateway","Capacity available?","L_Coord",4,doc=src(f"{AS} step 3"))
N("e_alt","task","Propose another date","L_Coord",4,"U",doc=src(f"{AS} step 3"))
N("e_endalt","endEvent","Other date proposed","L_Coord",5,"U",doc=src(f"{AS} step 3"))
N("e_quote","task","P4 · Write quote in Word and e-mail it as PDF","L_Coord",6,doc=src(f"{AS} step 4", f"{EV} Q1"),color=RED)
N("e_evgw","eventBasedGateway","Wait for reply","L_Coord",7,doc=src(f"{AS} step 5"))
N("e_acc","intermediateCatchEvent","Acceptance received","L_Coord",8,defn="message",doc=src(f"{AS} step 5"))
N("e_dec","intermediateCatchEvent","Decline received","L_Coord",9,"U",defn="message",doc=src("INFERRED from step 5"))
N("e_enddec","endEvent","Not booked","L_Coord",10,"U",doc=src("INFERRED"))
N("e_excel","task","P6 · Add row to Excel sheet 'Bestillinger'","L_Coord",10,doc=src(f"{AS} step 5", f"{EV} Q1"),color=RED)
N("e_gw2","exclusiveGateway","Wedding?","L_Coord",11,doc=src(f"{AS} step 6"))
N("e_dep","task","P7 · Send Vipps deposit request (sometimes forgotten)","L_Coord",12,"U",doc=src(f"{AS} step 6"),color=RED)
N("e_m2","exclusiveGateway","","L_Coord",13,doc="Merge gateway")
N("e_print","task","P8 · Print order and pin it on the kitchen board","L_Coord",14,doc=src(f"{AS} step 7", f"{EV} Q1"),color=RED)
N("e_gw4","exclusiveGateway","Changes received?","L_Coord",15,doc=src(f"{AS} step 8"))
N("e_upd","task","P9 · Update Excel and re-print (sometimes forgotten)","L_Coord",16,"U",doc=src(f"{AS} step 8", f"{EV} Q1"),color=RED)
N("e_m4","exclusiveGateway","","L_Coord",17,doc="Merge gateway")
N("e_call","task","P10 · Phone customer 7 days before to confirm numbers (if time)","L_Coord",18,doc=src(f"{AS} step 9"),color=RED)
N("k_prep","task","P11 · Prepare food from the printed order","L_Kitchen",19,doc=src(f"{AS} step 10", f"{EV} Q5"),color=RED)
N("d_del","task","Deliver food (address from printout, own phone)","L_Driver",20,doc=src(f"{AS} step 10", f"{ITN} 'Driver'"))
N("e_inv","task","P12 · Create invoice in Fiken or Vipps request manually","L_Coord",21,doc=src(f"{AS} step 11"),color=RED)
N("e_end","endEvent","Order completed","L_Coord",22,doc=src(f"{AS} step 11"))
N("o_start","startEvent","Monthly","L_Owner",19,defn="timer",doc=src(f"{AS} step 12"))
N("o_rec","task","Reconcile Fiken with the Excel sheet","L_Owner",20,doc=src(f"{AS} step 12"))
N("o_end","endEvent","Reconciled","L_Owner",21,doc=src(f"{AS} step 12"))
F = a.flow
for s, t, *r in [("c_start","c_send"),("c_send","c_quote"),("c_quote","c_gw"),("c_gw","c_acc","Yes"),("c_gw","c_dec","No"),
    ("c_dec","c_enddec"),("c_acc","c_gwW"),("c_gwW","c_pay","Yes"),("c_gwW","c_mW","No"),("c_pay","c_mW"),("c_mW","c_gwC"),
    ("c_gwC","c_chg","Yes"),("c_gwC","c_mC","No"),("c_chg","c_mC"),("c_mC","c_conf"),("c_conf","c_food"),("c_food","c_payinv"),("c_payinv","c_end"),
    ("e_start","e_read"),("e_read","e_cap"),("e_cap","e_gw1"),("e_gw1","e_alt","No"),("e_alt","e_endalt"),("e_gw1","e_quote","Yes"),
    ("e_quote","e_evgw"),("e_evgw","e_acc"),("e_evgw","e_dec"),("e_dec","e_enddec"),("e_acc","e_excel"),("e_excel","e_gw2"),
    ("e_gw2","e_dep","Yes"),("e_gw2","e_m2","No"),("e_dep","e_m2"),("e_m2","e_print"),("e_print","e_gw4"),("e_gw4","e_upd","Yes"),
    ("e_gw4","e_m4","No"),("e_upd","e_m4"),("e_m4","e_call"),("e_call","k_prep"),("k_prep","d_del"),("d_del","e_inv"),("e_inv","e_end"),
    ("o_start","o_rec"),("o_rec","o_end")]:
    F(s, t, *r)
M = a.message
M("c_send","e_start","Request"); M("e_alt","P_Customer","Alternative date"); M("e_quote","c_quote","Quote (PDF)")
M("c_acc","e_acc","Acceptance"); M("c_dec","e_dec","Decline"); M("e_dep","c_pay","Deposit request")
M("c_chg","e_upd","Changes"); M("e_call","c_conf","Confirmation call"); M("d_del","c_food","Food")
M("e_inv","c_payinv","Invoice / Vipps request")
a.note("Ann_legend", "Red task = step with a problem reported by a stakeholder (P1-P12). See 02_bpmn_problem-to-story-mapping_2026-10-22.md.", 0, 10, 420, 60)
dl = a.nodes["d_del"]; a.note("Ann_driver", "Not marked: no problem reported; the driver was not interviewed (ISS-13).", dl["x"] + 160, dl["y"] + 10, 270, 60)
orc = a.nodes["o_rec"]; a.note("Ann_owner", "Not marked: no stakeholder complaint documented for this step.", orc["x"] - 470, orc["y"] + 10, 250, 60)

# =================================================================== TO-BE
b = Diagram("tobe", 23)
b.pool("P_Customer", "Customer", [("L_C", "", ["U", "M"])])
pe = b.pool("P_EkteMat", "Ekte Mat AS", [("L_Sys", "Ekte Mat Online", ["M", "D"]), ("L_Coord", "Event coordinator", ["U", "M"]),
         ("L_Kitchen", "Kitchen", ["M"]), ("L_Driver", "Driver", ["M"]), ("L_Owner", "Owner", ["M"])])
yb = b.y
b.pool("P_Vipps", "Vipps (external)", [], process=False, collapsed=True, x=X_CONTENT + 7 * COLW, w=6 * COLW, y=yb)
b.pool("P_Fiken", "Fiken (external)", [], process=False, collapsed=True, x=X_CONTENT + 19.5 * COLW, w=3.2 * COLW, y=yb)
N = b.node
BL = Path(SRC["BL"]).name
N("c_start","startEvent","Catering need arises","L_C",0,doc=src(f"{AS} step 1 (INFERRED)"))
N("c_browse","task","Browse menus, prices, origin and allergens [US-01, US-05, US-06]","L_C",1,doc=src(f"{BL} US-01, US-05, US-06"),color=BLUE)
N("c_submit","task","Submit booking request with date, guest groups and allergies [US-02, US-03, US-07]","L_C",2,doc=src(f"{BL} US-02, US-03, US-07"),color=BLUE)
N("c_rcpt","intermediateCatchEvent","Receipt received [US-04]","L_C",3,defn="message",doc=src(f"{BL} US-04"))
N("c_evgw","eventBasedGateway","Wait for answer","L_C",4,doc=src(f"{BL} US-04 (INFERRED)"))
N("c_alt","intermediateCatchEvent","Alternative date or decline received","L_C",6,"U",defn="message",doc=src(f"{AS} step 3"))
N("c_endalt","endEvent","Not booked","L_C",7,"U",doc=src("INFERRED"))
N("c_conf","intermediateCatchEvent","Confirmation received [US-04]","L_C",7,defn="message",doc=src(f"{BL} US-04"))
N("c_gwdep","exclusiveGateway","Deposit requested?","L_C",8,doc=src(f"{BL} US-22 (UNRESOLVED, ISS-01)"))
N("c_pay","task","Pay deposit with Vipps [US-22]","L_C",9,"U",doc=src(f"{BL} US-22"),color=BLUE)
N("c_mdep","exclusiveGateway","","L_C",10,doc="Merge gateway")
N("c_remrcv","intermediateCatchEvent","Reminder received [US-12]","L_C",14,defn="message",doc=src(f"{BL} US-12"))
N("c_confirm","task","Confirm or change guest numbers and allergies online [US-11, US-12]","L_C",15,doc=src(f"{BL} US-11, US-12"),color=BLUE)
N("c_food","task","Receive or collect the food [US-14]","L_C",18,doc=src(f"{BL} US-14"))
N("c_pay2","task","Pay with Vipps or via monthly EHF invoice [US-21, US-23]","L_C",21,doc=src(f"{BL} US-21, US-23"),color=BLUE)
N("c_end","endEvent","Order completed","L_C",22,doc=src(f"{AS} step 11"))

N("s_start","startEvent","Booking request received","L_Sys",2,defn="message",doc=src(f"{BL} US-02"))
N("s_store","task","Store request, send receipt, check capacity [US-02, US-04, US-10]","L_Sys",3,doc=src(f"{BL} US-02, US-04, US-10"),color=BLUE)
N("e_review","task","Review request in capacity calendar [US-09, US-10]","L_Coord",4,doc=src(f"{BL} US-09, US-10"),color=BLUE)
N("e_gw","exclusiveGateway","Accept request?","L_Coord",5,doc=src(f"{AS} step 3; {BL} US-02 (review step ASSUMPTION)"))
N("e_decl","task","Propose another date or decline","L_Coord",6,"U",doc=src(f"{AS} step 3"))
N("e_enddecl","endEvent","Not booked","L_Coord",7,"U",doc=src("INFERRED"))
N("s_confirm","task","Confirm order and notify customer [US-04]","L_Sys",7,doc=src(f"{BL} US-04"),color=BLUE)
N("s_gwdep","exclusiveGateway","Deposit required? (ISS-01)","L_Sys",8,doc=src(f"{BL} US-22; ISS-01"))
N("s_dep","task","Request deposit via Vipps [US-21, US-22]","L_Sys",9,"D",doc=src(f"{BL} US-21, US-22"),color=BLUE)
N("s_mdep","exclusiveGateway","","L_Sys",10,doc="Merge gateway")
N("s_kview","task","Show order on kitchen overview [US-15]","L_Sys",11,doc=src(f"{BL} US-15"),color=BLUE)
N("k_conf","task","Confirm allergy information [US-16]","L_Kitchen",12,doc=src(f"{BL} US-16"),color=BLUE)
N("s_timer","intermediateCatchEvent","7 days before event","L_Sys",13,defn="timer",doc=src(f"{BL} US-12"))
N("s_rem","task","Send reminder for final guest numbers [US-12]","L_Sys",14,doc=src(f"{BL} US-12"),color=BLUE)
N("s_upd","task","Update order and kitchen overview [US-09, US-11]","L_Sys",15,doc=src(f"{BL} US-09, US-11"),color=BLUE)
N("k_prep","task","Prepare food from kitchen overview and prep list [US-15, US-20]","L_Kitchen",16,doc=src(f"{BL} US-15, US-20"),color=BLUE)
N("k_gw","exclusiveGateway","Delivery or pick-up? [US-14]","L_Kitchen",17,doc=src(f"{BL} US-14"))
N("d_del","task","Deliver to the address and time in the order [US-14]","L_Driver",18,doc=src(f"{BL} US-14"),color=BLUE)
N("k_pick","task","Hand over food at pick-up [US-14]","L_Kitchen",19,doc=src(f"{BL} US-14"),color=BLUE)
N("k_m","exclusiveGateway","","L_Kitchen",20,doc="Merge gateway")
N("s_inv","task","Create invoice in Fiken or capture Vipps payment [US-21, US-23, US-24]","L_Sys",21,doc=src(f"{BL} US-21, US-23, US-24"),color=BLUE)
N("s_end","endEvent","Order completed","L_Sys",22,doc=src(f"{AS} step 11"))
F = b.flow
for s, t, *r in [("c_start","c_browse"),("c_browse","c_submit"),("c_submit","c_rcpt"),("c_rcpt","c_evgw"),("c_evgw","c_conf"),
    ("c_evgw","c_alt"),("c_alt","c_endalt"),("c_conf","c_gwdep"),("c_gwdep","c_pay","Yes"),("c_gwdep","c_mdep","No"),("c_pay","c_mdep"),
    ("c_mdep","c_remrcv"),("c_remrcv","c_confirm"),("c_confirm","c_food"),("c_food","c_pay2"),("c_pay2","c_end"),
    ("s_start","s_store"),("s_store","e_review"),("e_review","e_gw"),("e_gw","e_decl","No","top"),("e_decl","e_enddecl"),
    ("e_gw","s_confirm","Yes","right"),("s_confirm","s_gwdep"),("s_gwdep","s_dep","Yes"),("s_gwdep","s_mdep","No"),("s_dep","s_mdep"),
    ("s_mdep","s_kview"),("s_kview","k_conf"),("k_conf","s_timer"),("s_timer","s_rem"),("s_rem","s_upd"),("s_upd","k_prep"),
    ("k_prep","k_gw"),("k_gw","d_del","Delivery"),("k_gw","k_pick","Pick-up"),("d_del","k_m"),("k_pick","k_m"),("k_m","s_inv"),("s_inv","s_end")]:
    F(s, t, *r)
M = b.message
M("c_submit","s_start","Booking request"); M("s_store","c_rcpt","Receipt"); M("e_decl","c_alt","Alternative / decline")
M("s_confirm","c_conf","Confirmation"); M("s_dep","c_pay","Deposit request"); M("s_dep","P_Vipps","Payment request",-20,-20)
M("P_Vipps","s_dep","Payment confirmed",20,20); M("s_rem","c_remrcv","Reminder"); M("c_confirm","s_upd","Final numbers / changes")
M("d_del","c_food","Food",0,-25); M("k_pick","c_food","Food (pick-up)",0,25)
M("s_inv","c_pay2","Invoice / payment"); M("s_inv","P_Fiken","Invoice data")
b.note("Ann_legend", "Blue = supported by Ekte Mat Online. [US-xx] = user story in 01_Requirements/EkteMat_backlog_v1.xlsx.", 0, 10, 420, 60)
gd = b.nodes["s_gwdep"]
b.note("Ann_dep", "Deposit scope is unresolved: all bookings or weddings only? (ISS-01)", gd["cx"] - 125 + 60, b.lane("L_Coord")[1]["y"] + 25, 250, 60)
b.ann[-1] = ("Ann_dep", b.ann[-1][1], gd["cx"] - 80, b.lane("L_Coord")[1]["y"] + RH + 28, 200, 60, "s_gwdep")
cl = b.lane("L_Coord")[1]
b.note("Ann_phone", "Phone and e-mail orders are entered by the coordinator into the same order record (US-09; ISS-12).", X_CONTENT + 9.5 * COLW, cl["y"] + RH + 28, 300, 60)
ol = b.lane("L_Owner")[1]
b.note("Ann_owner", "No per-order task: the monthly manual reconciliation is replaced by the Fiken integration (US-24, INFERRED).", X_CONTENT + 0.5 * COLW, ol["y"] + 28, 420, 60)

# ------------------------------------------------------- problem mapping
def Q(k, ref, t):
    hay = EMAIL.get(ref, "") if k == "CSV" else TEXT[k]
    if norm(t) not in hay: errors.append(f"quote not found {k} {ref}: {t}")
    name = CSVN if k == "CSV" else Path(SRC[k]).name
    return f'{name} [{ref}]: "{t}"'
PROB = [
 ("P1","Customer: Send request by e-mail, phone or web form","Requests are lost (spam folder, failing web form, unanswered phone).",
  [Q("OWN","Q1","Last December we found three julebord requests in the spam folder after the date had passed."),
   Q("CSV","E023","I tried the contact form on your website three times and got an error."),
   Q("CSV","E003","I called yesterday but nobody picked up.")],["US-02","US-09"],"Submit booking request online; stored in one order record","DIRECT"),
 ("P2","Coordinator: Read request","Replies take 1-2 days, up to a week in peak season; customers go elsewhere.",
  [Q("EVC","Q2","On a normal week one or two days. In December and in May it can be a week. People get annoyed."),
   Q("CSV","E006","I sent a request 6 days ago and have not heard back.")],["US-02","US-04"],"Request stored instantly; automatic receipt","DIRECT"),
 ("P3","Coordinator: Check capacity in Google Calendar","Capacity is judged by gut feeling; risk of overbooking.",
  [Q("ASIS","step 3","If the day is \"full\" (gut feeling), she proposes another date."),
   Q("EVC","Q4","A calendar that shows how many guests we already have per day, so I do not overbook.")],["US-10","US-03"],"Capacity check and calendar; customers see available dates","DIRECT"),
 ("P4","Coordinator: Write quote in Word and e-mail as PDF","Manual quotes delay customers who need prices quickly.",
  [Q("ASIS","step 4","Coordinator writes a quote in Word from a template and e-mails it as PDF."),
   Q("CSV","E015","We need a quote for a seminar lunch 80 people by Friday for internal approval.")],["US-01"],"Customers browse menus and prices online","INFERRED (that online prices reduce the need for quotes)"),
 ("P5","Customer: Accept quote by e-mail","No confirmation is sent after acceptance; customers do not know if the order is confirmed.",
  [Q("CSV","E011","Is our order for tomorrow confirmed? We never got a confirmation e-mail."),
   Q("CORP","Q1","Sometimes it arrives Monday morning, which is too late for me.")],["US-04"],"Confirm order and notify customer","DIRECT"),
 ("P6","Coordinator: Add row to Excel sheet","Double entry in Excel; the sheet and printouts get out of sync.",
  [Q("EVC","Q1","when they say yes I add a row in \"Bestillinger 2025.xlsx\""),
   Q("EVC","Q1","I have to remember to update both the sheet and the printout.")],["US-09"],"One order record in the system","DIRECT"),
 ("P7","Coordinator: Send Vipps deposit request","The deposit request is sometimes forgotten; no-shows at weddings.",
  [Q("ASIS","step 6","For weddings, the coordinator sends a Vipps payment request for a deposit (sometimes forgotten)."),
   Q("OWN","Q2","We have had too many no-shows at weddings.")],["US-22"],"Request deposit via Vipps (scope UNRESOLVED, ISS-01)","UNRESOLVED"),
 ("P8","Coordinator: Print order and pin on kitchen board","Paper orders must be re-printed after every change.",
  [Q("EVC","Q1","Then I print the order and put it on the kitchen board."),
   Q("CHF","Q1","One screen in the kitchen.")],["US-15","US-09"],"Show order on kitchen overview","DIRECT"),
 ("P9","Customer: Report changes by phone/e-mail; Coordinator: Update Excel and re-print","Changes arrive by phone and are sometimes not updated.",
  [Q("EVC","Q1","Changes in guest numbers come by phone, and I have to remember to update both the sheet and the printout. Sometimes I forget."),
   Q("CSV","E003","we need to change from 40 to 55 guests for our event next Thursday.")],["US-11","US-09"],"Customer changes online; system updates order and kitchen overview","DIRECT"),
 ("P10","Coordinator: Phone customer 7 days before","Final numbers are only confirmed if the coordinator has time.",
  [Q("ASIS","step 9","7 days before the event the coordinator phones the customer to confirm final numbers (if she has time)."),
   Q("EVC","Q4","automatic reminders to customers about final guest numbers seven days before the event.")],["US-12"],"Automatic 7-day reminder","DIRECT"),
 ("P11","Kitchen: Prepare food from the printed order","Allergies and diets can be missed (2024 nut incident, missing vegan dish).",
  [Q("EVC","Q5","We had a nut incident in 2024 - nobody was hurt, but it was close."),
   Q("CSV","E017","The vegan dish was missing on the delivery yesterday (order for 30).")],["US-15","US-16","US-07"],"Kitchen overview with allergies in red; kitchen confirms allergies","DIRECT"),
 ("P12","Coordinator: Create invoice in Fiken or Vipps request manually","Manual invoicing; PDF invoices rejected by corporate customers.",
  [Q("ASIS","step 11","After the event the coordinator creates an invoice in Fiken manually"),
   Q("CSV","E004","Last invoice was a PDF by e-mail and was rejected."),
   Q("CORP","Q3","One EHF invoice per month, with our cost-centre code on each line.")],["US-24","US-23","US-21"],"Create invoice in Fiken or capture Vipps payment","DIRECT"),
]
# P-labels in AS-IS must match the table exactly
labels = {m for n in a.nodes.values() for m in re.findall(r"^P(\d+) ·", n["name"])}
if labels != {p[0][1:] for p in PROB}: errors.append(f"P-labels mismatch: {sorted(labels)}")
for p in PROB:
    for sid in p[4]:
        if sid not in STORIES: errors.append(f"{p[0]}: unknown story {sid}")
        if sid not in stories_in(b): errors.append(f"{p[0]}: {sid} not shown in TO-BE")
for d in (a, b):
    for sid in stories_in(d):
        if sid not in STORIES: errors.append(f"{d.name}: unknown story {sid}")
    for n in d.nodes.values():
        if not n["doc"]: errors.append(f"{d.name}: {n['id']} has no source")

OUT.mkdir(parents=True, exist_ok=True)
write_bpmn(a, OUT / f"02_bpmn_as-is-order-process_{DATE}.bpmn")
write_bpmn(b, OUT / f"02_bpmn_to-be-order-process_{DATE}.bpmn")

def short(sid):
    m = re.search(r"I want (.+?) so that", STORIES[sid]); return m.group(1) if m else STORIES[sid]
md = [f"# BPMN models: AS-IS and TO-BE order process ({DATE})", "",
 "Project: Ekte Mat Online (INFO212). Models built from `02_process_as-is-order-handling_2026-08-15.md`, the four stakeholder interviews and `01_Requirements/EkteMat_backlog_v1.xlsx`.", "",
 "## Files", "",
 "| File | Content |", "|---|---|",
 f"| `02_bpmn_as-is-order-process_{DATE}.bpmn` | AS-IS diagram source (BPMN 2.0 XML; opens in Camunda Modeler or demo.bpmn.io) |",
 f"| `02_bpmn_as-is-order-process_{DATE}.svg` / `.png` | AS-IS rendered image |",
 f"| `02_bpmn_to-be-order-process_{DATE}.bpmn` | TO-BE diagram source |",
 f"| `02_bpmn_to-be-order-process_{DATE}.svg` / `.png` | TO-BE rendered image |",
 f"| `02_bpmn_build_{DATE}.py` | Generator and checks (layout, labels, quotes, story IDs) |",
 f"| `02_bpmn_render_{DATE}.js` | Renders .bpmn to .svg/.png with bpmn-js 17.11.1 in headless Chromium |", "",
 "## Notation choices", "",
 "- **Pools and lanes:** *Customer* is its own pool because message flows may only connect different pools. *Ekte Mat AS* is one pool with the lanes Event coordinator, Kitchen, Driver and Owner; in TO-BE it also has the lane *Ekte Mat Online*.",
 "- **External services:** Vipps and Fiken are collapsed (black-box) pools in TO-BE.",
 "- **Elements used:** start events (message, timer, none), end events, tasks, exclusive gateways (split with labelled Yes/No flows and unlabelled merges), event-based gateways (waiting for a reply), intermediate message and timer catch events, sequence flows inside a pool and message flows between pools.",
 "- **Problem marking (AS-IS):** red tasks labelled P1-P12. The monthly reconciliation and the driver's delivery are not marked because no stakeholder reports a problem there (see annotations).",
 "- **Sources:** every element carries a `documentation` entry naming its source file and step/question. Open an element's properties in a BPMN tool to see it.", "",
 "## Problems in the AS-IS process and the user stories that fix them", "",
 "| ID | AS-IS step | Problem | Stakeholder evidence (verbatim) | Fixed by user story | TO-BE step | Evidence status |",
 "|---|---|---|---|---|---|---|"]
for pid, step, prob, quotes, sids, tobe, status in PROB:
    st = "<br>".join(f"**{s}**: {short(s)}" for s in sids)
    md.append(f"| {pid} | {step} | {prob} | {'<br>'.join(quotes)} | {st} | {tobe} | {status} |")
used = sorted(set(stories_in(b)))
notused = [s for s in sorted(STORIES) if s not in used]
md += ["", "## Coverage", "",
 f"- User stories shown in the TO-BE diagram ({len(used)}): {', '.join(used)}.",
 f"- Not shown ({len(notused)}): {', '.join(notused)}. These are menu/supplier administration, corporate account functions, privacy requests or cancellation, which run outside the single-order flow. US-13 (cancellation) is omitted because cancellation terms are missing (ISS-04).", "",
 "## Simplifications and open points", "",
 "- **Changes (AS-IS):** customer changes are drawn at one point in the flow (gateway *Changes received?*); in reality they can arrive at any time.",
 "- **Decline branch:** the customer's *Decline quote* path is INFERRED; the source only describes acceptance.",
 "- **Coordinator review (TO-BE):** a coordinator review step is an ASSUMPTION; whether requests are confirmed automatically is not decided (US-02, US-10).",
 "- **Deposit gateway (TO-BE):** the scope (all bookings or weddings only) is unresolved (ISS-01).",
 "- **Deposit payment:** the customer pays in the Vipps app; this is simplified to a message from Ekte Mat Online.",
 "- **Owner lane (TO-BE):** the lane is intentionally empty of tasks.", "",
 "## Validation performed", "",
 "- `bpmnlint` 10.3.1 with the `bpmnlint:recommended` rule set: 0 problems for both diagrams (the linter was also shown to flag a deliberately broken copy).",
 "- Import into `bpmn-js` 17.11.1: 0 import warnings for both diagrams.",
 "- Generator checks: no sequence or message flow crosses another element, annotation or explicit label; every element has a source entry; every story ID exists in the backlog; every quote in the table occurs verbatim in its source.",
 "- Visual check of the rendered PNGs.",
 "- Not checked: opening the files in Camunda Modeler or Signavio.", ""]
(OUT / f"02_bpmn_problem-to-story-mapping_{DATE}.md").write_text("\n".join(md), encoding="utf-8")

if errors:
    print("CHECKS FAILED"); print("\n".join(errors)); sys.exit(1)
print("OK: layout, sources, story IDs and quotes checked.")
print("AS-IS nodes", len(a.nodes), "seq", len(a.seq), "msg", len(a.msg), "| TO-BE nodes", len(b.nodes), "seq", len(b.seq), "msg", len(b.msg))
print("stories in TO-BE", used)
