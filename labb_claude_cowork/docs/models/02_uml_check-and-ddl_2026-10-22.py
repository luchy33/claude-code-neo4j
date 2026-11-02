"""Model checks and SQL DDL generation for Ekte Mat Online (INFO212).

The four PlantUML files are the models. This script
  1. parses them and runs consistency rules R1-R6 (see RULES below),
  2. transforms the class diagram into PostgreSQL DDL (model-driven step) and
     logs every mapping decision,
  3. optionally runs schema tests against a live PostgreSQL database.

Usage:
  python -I 02_uml_check-and-ddl_2026-10-22.py <repo_root> <out_dir> [--test "<psql args>"]
Inputs: 02_uml_*.puml in <repo_root>/02_Analysis_and_models, backlog in 01_Requirements.
"""
import re, sys, json, subprocess, collections
from pathlib import Path
import openpyxl

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
DATE = "2026-10-22"
MD = REPO / "02_Analysis_and_models"
F_UC = MD / f"02_uml_use-case_{DATE}.puml"
F_CL = MD / f"02_uml_domain-class_{DATE}.puml"
F_SQ = MD / f"02_uml_sequence_standing-order-ehf-invoice_{DATE}.puml"
F_SM = MD / f"02_uml_state-machine_order_{DATE}.puml"
ws = openpyxl.load_workbook(REPO / "01_Requirements/EkteMat_backlog_v1.xlsx", read_only=True)["User stories"]
STORY = {r[0]: (r[5], r[3]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}
MS = {k for k, (p, _) in STORY.items() if p in ("Must", "Should")}
lines = lambda f: [l.rstrip() for l in f.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("'")]

# --------------------------------------------------------------- parse class diagram
CLASSES, ENUMS, ABSTRACT, PARENT, ASSOC, CONSTRAINT_NOTES = {}, {}, set(), {}, [], []
cur = None
for l in lines(F_CL):
    s = l.strip()
    m = re.match(r"^(abstract class|class|enum)\s+(\w+)\s*\{$", s)
    if m:
        kind, name = m.groups(); cur = (kind, name)
        if kind == "enum": ENUMS[name] = []
        else: CLASSES[name] = []
        if kind == "abstract class": ABSTRACT.add(name)
        continue
    if s == "}": cur = None; continue
    if cur:
        if cur[0] == "enum": ENUMS[cur[1]].append(s); continue
        m = re.match(r"^(\w+)\s*:\s*(\w+)\s*(\[[^\]]+\])?\s*(.*)$", s)
        if not m: raise SystemExit(f"cannot parse attribute: {s}")
        n, t, mult, cons = m.groups()
        CLASSES[cur[1]].append(dict(name=n, type=t, mult=(mult or "[1]")[1:-1], cons=re.findall(r"\{([^}]+)\}", cons)))
        continue
    m = re.match(r"^(\w+)\s+<\|--\s+(\w+)$", s)
    if m: PARENT[m.group(2)] = m.group(1); continue
    m = re.match(r'^(\w+)\s+"([^"]+)"\s+(\*--|--)\s+"([^"]+)"\s+(\w+)\s*(?::\s*(.+?))?\s*[<>]?$', s)
    if m:
        a, ma, kind, mb, b, label = m.groups()
        ASSOC.append(dict(a=a, ma=ma, b=b, mb=mb, comp=kind == "*--", label=(label or "").strip(" <>")))

def bounds(m):
    if ".." in m: lo, hi = m.split(".."); return int(lo), (None if hi == "*" else int(hi))
    return (0, None) if m == "*" else (int(m), int(m))

# --------------------------------------------------------------- parse other diagrams
USECASES = [(m.group(2), m.group(1)) for m in (re.search(r'usecase\s+"([^"]+)"\s+as\s+(\w+)', l) for l in lines(F_UC)) if m]
SEQ_PART, SEQ_MSG = [], []
for l in lines(F_SQ):
    s = l.strip()
    m = re.match(r'^(actor|participant|boundary|control|entity|database)\s+"([^"]+)"\s+as\s+(\w+)', s)
    if m: SEQ_PART.append(dict(kind=m.group(1), label=m.group(2), alias=m.group(3))); continue
    m = re.match(r"^(\w+)\s*-+>+\s*(\w+)\s*:\s*(.+)$", s)
    if m: SEQ_MSG.append(dict(src=m.group(1), dst=m.group(2), text=m.group(3).replace("\\n", " ")))
SM_TRANS, SM_STATES = [], set()
for l in lines(F_SM):
    m = re.match(r"^(\[\*\]|\w+)\s+-->\s+(\[\*\]|\w+)\s*(?::\s*(.*))?$", l.strip())
    if m:
        SM_TRANS.append((m.group(1), m.group(2), (m.group(3) or "").replace("\\n", " ")))
        SM_STATES |= {x for x in m.groups()[:2] if x != "[*]"}
    m2 = re.match(r"^(\w+)\s*:\s*(.+)$", l.strip())
    if m2 and m2.group(1) not in ("title",) and not m: SM_TRANS.append((m2.group(1), m2.group(1), m2.group(2)))
upper_snake = lambda n: re.sub(r"(?<!^)(?=[A-Z])", "_", n).upper()
snake = lambda n: re.sub(r"(?<!^)(?=[A-Z])", "_", n).lower()

# --------------------------------------------------------------- consistency rules
RULES = {
 "R1": "Every use case is traceable to at least one user story, and each cited story exists and is Must or Should.",
 "R2": "Every Must/Should story is covered by at least one use case (coverage, reverse direction).",
 "R3": "Every class used in the sequence diagram exists in the class diagram.",
 "R4": "Every state in the Order state machine is a value of OrderStatus, and every OrderStatus value is a state.",
 "R5": "Every constant (UPPER_CASE) used in sequence messages is a value of an enumeration in the class diagram.",
 "R6": "Every attribute assigned in a sequence message exists in the receiving class; every story cited in the sequence and state diagrams is Must or Should.",
}
V = []  # (rule, diagram, element, problem, fix)
for alias, label in USECASES:
    ids = re.findall(r"US-\d\d", label)
    uc = label.split("\\n")[0]
    if not ids: V.append(("R1", "Use case", uc, "No user story cited", "Add a story or remove the use case"))
    for i in ids:
        if i not in STORY: V.append(("R1", "Use case", uc, f"{i} does not exist in the backlog", "Correct the ID"))
        elif i not in MS: V.append(("R1", "Use case", uc, f"{i} is {STORY[i][0]}, not Must/Should", "Remove or re-prioritise"))
covered = {i for _, l in USECASES for i in re.findall(r"US-\d\d", l)}
for i in sorted(MS - covered): V.append(("R2", "Use case", i, f"{STORY[i][0]} story not covered by any use case", "Add a use case"))

part_class = {}
for p in SEQ_PART:
    if ":" in p["label"]:
        cls = p["label"].split(":", 1)[1].strip()
        part_class[p["alias"]] = cls
        if cls not in CLASSES: V.append(("R3", "Sequence", p["label"], f"Class {cls} is not in the class diagram", "Add the class or rename the participant"))
enum_values = {v for vals in ENUMS.values() for v in vals}
for msg in SEQ_MSG:
    for tok in re.findall(r"\b[A-Z][A-Z_]{2,}\b(?!-\d)", msg["text"]):
        if tok not in enum_values: V.append(("R5", "Sequence", msg["text"], f"{tok} is not an enumeration value", "Use a defined value"))
    cls = part_class.get(msg["dst"])
    if cls:
        attrs = {a["name"] for c in [cls, PARENT.get(cls)] if c for a in CLASSES.get(c, [])}
        for att in re.findall(r"\b([a-z]\w*)\s*=", msg["text"]):
            if att not in attrs: V.append(("R6", "Sequence", msg["text"], f"{att} is not an attribute of {cls}", "Use an existing attribute"))
status_vals = set(ENUMS.get("OrderStatus", []))
for st in sorted(SM_STATES):
    if upper_snake(st) not in status_vals: V.append(("R4", "State machine", st, "State has no OrderStatus value", "Align names"))
for v in sorted(status_vals - {upper_snake(s) for s in SM_STATES}):
    V.append(("R4", "Class diagram", f"OrderStatus.{v}", "Enum value has no state", "Align names"))
for diag, texts in (("Sequence", [m["text"] for m in SEQ_MSG] + [l for l in lines(F_SQ) if l.strip().startswith("==")]),
                    ("State machine", [t[2] for t in SM_TRANS])):
    for t in texts:
        for i in re.findall(r"US-\d\d", t):
            if i not in STORY: V.append(("R6", diag, t.strip(), f"{i} does not exist", "Correct the ID"))
            elif i not in MS: V.append(("R6", diag, t.strip(), f"{i} is {STORY[i][0]}, not Must/Should", "Accept with note, or re-prioritise"))

# --------------------------------------------------------------- DDL generation (MDE)
RESERVED = {"order", "user", "group", "table", "select", "check"}
DEC = []  # mapping decisions: (model element, rule, SQL result)
def table_name(cls):
    t = snake(cls)
    return "customer_order" if t in RESERVED else t
TYPE = {"String": "TEXT", "Integer": "INTEGER", "Boolean": "BOOLEAN", "Date": "DATE",
        "DateTime": "TIMESTAMPTZ", "Time": "TIME", "Money": "NUMERIC(12,2)"}
for cls in CLASSES:
    if table_name(cls) != snake(cls): DEC.append((f"class {cls}", "Reserved SQL word avoided", f"table {table_name(cls)}"))
TABLES = collections.OrderedDict()   # name -> dict(cols=[...], cons=[...], deps=set())
def T(name): return TABLES.setdefault(name, dict(cols=[], cons=[], deps=set(), idx=[], comment=""))
def pk_col(cls): return f"{snake(PARENT[cls])}_id" if cls in PARENT else "id"

ddl_types = []
for e, vals in ENUMS.items():
    ddl_types.append(f"CREATE TYPE {snake(e)} AS ENUM ({', '.join(repr(v) for v in vals)});")
    DEC.append((f"enum {e}", "Enumeration -> PostgreSQL ENUM type", f"TYPE {snake(e)}"))
for ab in ABSTRACT:
    subs = [c for c, p in PARENT.items() if p == ab]
    ddl_types.append(f"CREATE TYPE {snake(ab)}_type AS ENUM ({', '.join(repr(upper_snake(s)) for s in subs)});")
    DEC.append((f"abstract {ab}", "Discriminator type for subclasses", f"TYPE {snake(ab)}_type"))

for cls, attrs in CLASSES.items():
    t = T(table_name(cls))
    if cls in PARENT:
        par = PARENT[cls]; pt = table_name(par); tag = upper_snake(cls)
        t["cols"].append(f"{pk_col(cls)} BIGINT PRIMARY KEY")
        t["cols"].append(f"{snake(par)}_type {snake(par)}_type NOT NULL DEFAULT '{tag}' CHECK ({snake(par)}_type = '{tag}')")
        t["cons"].append(f"FOREIGN KEY ({pk_col(cls)}, {snake(par)}_type) REFERENCES {pt} (id, {snake(par)}_type) ON DELETE CASCADE")
        t["deps"].add(pt)
        DEC.append((f"{par} <|-- {cls}", "Generalisation -> class-table inheritance: subclass table shares the parent key; "
                    "composite FK (id, type) makes a row valid only for the matching subtype", f"{table_name(cls)}.customer_id PK/FK -> {pt}.id"))
    else:
        t["cols"].append("id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY")
        DEC.append((f"class {cls}", "Class -> table with surrogate key", f"{table_name(cls)}.id IDENTITY PK"))
    if cls in ABSTRACT:
        t["cols"].append(f"{snake(cls)}_type {snake(cls)}_type NOT NULL")
        t["cons"].append(f"UNIQUE (id, {snake(cls)}_type)")
    for a in attrs:
        col = snake(a["name"]); typ = snake(a["type"]) if a["type"] in ENUMS else TYPE[a["type"]]
        lo, hi = bounds(a["mult"])
        null = "" if lo == 0 else " NOT NULL"
        extra = ""
        for c in a["cons"]:
            if c == "unique": extra += " UNIQUE"
            elif re.match(r"^(>=|>)\s*\d+$", c): extra += f" CHECK ({col} {c})"
        t["cols"].append(f"{col} {typ}{null}{extra}")
        DEC.append((f"{cls}.{a['name']} : {a['type']} [{a['mult']}]" + ("".join(" {%s}" % c for c in a["cons"])),
                    ("[0..1] -> nullable" if lo == 0 else "[1] -> NOT NULL") + (f"; {a['type']} -> {typ}") +
                    ("; {unique} -> UNIQUE" if "unique" in a["cons"] else "") +
                    ("".join(f"; {{{c}}} -> CHECK" for c in a["cons"] if c != "unique")),
                    f"{table_name(cls)}.{col} {typ}{null}{extra}"))

LOWER_BOUND_TRIGGERS = []
def ref(cls): return table_name(cls), pk_col(cls)
for x in ASSOC:
    a, b, (alo, ahi), (blo, bhi) = x["a"], x["b"], bounds(x["ma"]), bounds(x["mb"])
    desc = f'{a} "{x["ma"]}" {"*--" if x["comp"] else "--"} "{x["mb"]}" {b}' + (f' : {x["label"]}' if x["label"] else "")
    if ahi == 1 and (bhi is None or bhi > 1) or bhi == 1 and (ahi is None or ahi > 1):
        one, many, (olo, _), (mlo, _) = (a, b, (alo, ahi), (blo, bhi)) if ahi == 1 else (b, a, (blo, bhi), (alo, ahi))
        rt, rc = ref(one); mt = table_name(many)
        col = f"{table_name(one)}_id"
        null = "" if olo == 0 else " NOT NULL"
        ondel = "CASCADE" if x["comp"] and one == a else ("SET NULL" if olo == 0 else "RESTRICT")
        T(mt)["cols"].append(f"{col} BIGINT{null}")
        T(mt)["cons"].append(f"FOREIGN KEY ({col}) REFERENCES {rt} ({rc}) ON DELETE {ondel}")
        T(mt)["idx"].append(col); T(mt)["deps"].add(rt)
        rule = (f"one-to-many -> FK in the 'many' table ({mt}); " + ("lower bound 0 on the 'one' end -> nullable FK"
                if olo == 0 else "lower bound 1 on the 'one' end -> NOT NULL FK") +
                f"; ON DELETE {ondel} (" + ("composition: parts die with the whole" if ondel == "CASCADE" else
                "optional link is cleared" if ondel == "SET NULL" else "referenced row cannot be deleted while in use") + ")")
        res = f"{mt}.{col} -> {rt}.{rc}{null} ON DELETE {ondel}"
        if mlo >= 1:
            LOWER_BOUND_TRIGGERS.append((rt, rc, mt, col, f"{one} must have at least {mlo} {many}"))
            rule += f"; lower bound {mlo} on the 'many' end cannot be expressed by a FK -> deferred constraint trigger"
        DEC.append((desc, rule, res))
    elif ahi == 1 and bhi == 1:
        # one-to-one: FK in the optional side, pointing to the side it must belong to
        opt, man = (b, a) if blo == 0 else (a, b)
        mlo = alo if opt == b else blo
        rt, rc = ref(man); ot = table_name(opt); col = f"{table_name(man)}_id"
        null = "" if mlo == 0 else " NOT NULL"
        ondel = "CASCADE" if x["comp"] else "RESTRICT"
        T(ot)["cols"].append(f"{col} BIGINT{null} UNIQUE")
        T(ot)["cons"].append(f"FOREIGN KEY ({col}) REFERENCES {rt} ({rc}) ON DELETE {ondel}")
        T(ot)["deps"].add(rt)
        DEC.append((desc, f"one-to-one ({x['ma']} : {x['mb']}) -> FK in the optional side ({ot}) with UNIQUE so each {man} has at most one {opt}"
                    f"; {'NOT NULL because each ' + opt + ' belongs to exactly one ' + man if null else 'nullable'}; ON DELETE {ondel}",
                    f"{ot}.{col} -> {rt}.{rc}{null} UNIQUE ON DELETE {ondel}"))
    else:
        jt = f"{snake(a)}_{snake(b)}"
        (at, ac), (bt, bc) = ref(a), ref(b)
        t = T(jt)
        ca, cb = f"{table_name(a)}_id", f"{table_name(b)}_id"
        t["cols"] += [f"{ca} BIGINT NOT NULL", f"{cb} BIGINT NOT NULL"]
        t["cons"] += [f"PRIMARY KEY ({ca}, {cb})",
                      f"FOREIGN KEY ({ca}) REFERENCES {at} ({ac}) ON DELETE CASCADE",
                      f"FOREIGN KEY ({cb}) REFERENCES {bt} ({bc}) ON DELETE RESTRICT"]
        t["idx"].append(cb); t["deps"] |= {at, bt}
        rule = (f"many-to-many -> junction table {jt} with composite PK (no duplicate links); "
                f"ON DELETE CASCADE from {a} (owner end, left), RESTRICT from {b} (cannot delete a {b} that is in use)")
        for (side, lo, other) in ((a, blo, b), (b, alo, a)):
            if lo >= 1:
                st, sc = ref(side)
                LOWER_BOUND_TRIGGERS.append((st, sc, jt, f"{table_name(side)}_id", f"{side} must have at least {lo} {other}"))
                rule += f"; lower bound {lo} ({side} needs >= {lo} {other}) -> deferred constraint trigger"
        DEC.append((desc, rule, f"TABLE {jt}"))

for ab in ABSTRACT:
    subs = [c for c, p in PARENT.items() if p == ab]
    DEC.append((f"abstract class {ab}", "Abstract -> every row must have exactly one subtype row: discriminator column + deferred trigger",
                f"{table_name(ab)}.{snake(ab)}_type + trigger"))

def topo():
    done, order = set(), []
    def visit(n, stack=()):
        if n in done: return
        if n in stack: raise SystemExit(f"cycle at {n}")
        for d in sorted(TABLES[n]["deps"]):
            if d != n: visit(d, stack + (n,))
        done.add(n); order.append(n)
    for n in TABLES: visit(n)
    return order

out = [f"-- Ekte Mat Online - PostgreSQL schema generated from 02_uml_domain-class_{DATE}.puml",
       f"-- Generator: 02_uml_check-and-ddl_{DATE}.py. Do not edit by hand: change the model and regenerate.",
       "-- Money columns are NOK. Every mapping decision is listed in 02_sql_mapping-decisions_" + DATE + ".md.", "",
       "BEGIN;", ""] + ddl_types + [""]
for n in topo():
    t = TABLES[n]
    body = ",\n  ".join(t["cols"] + t["cons"])
    out.append(f"CREATE TABLE {n} (\n  {body}\n);")
    for c in t["idx"]:
        out.append(f"CREATE INDEX {n}_{c}_idx ON {n} ({c});")
    out.append("")
DEC.append(("every FK column", "PostgreSQL does not index FK columns automatically -> one index per FK (not needed where UNIQUE/PK already indexes it)", "CREATE INDEX ..._idx"))
for i, (pt, pc, ct, cc, why) in enumerate(LOWER_BOUND_TRIGGERS, 1):
    fn = f"chk_min_{ct}_{cc}"
    out += [f"-- Multiplicity lower bound: {why}",
            f"CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$",
            "DECLARE pid BIGINT;", "BEGIN",
            f"  IF TG_TABLE_NAME = '{pt}' THEN pid := NEW.{pc}; ELSE pid := OLD.{cc}; END IF;",
            f"  IF EXISTS (SELECT 1 FROM {pt} WHERE {pc} = pid)",
            f"     AND NOT EXISTS (SELECT 1 FROM {ct} WHERE {cc} = pid) THEN",
            f"    RAISE EXCEPTION 'Multiplicity violated: {why} (id %)', pid;",
            "  END IF;", "  RETURN NULL;", "END $$;",
            f"CREATE CONSTRAINT TRIGGER {fn}_p AFTER INSERT ON {pt} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {fn}();",
            f"CREATE CONSTRAINT TRIGGER {fn}_c AFTER DELETE OR UPDATE OF {cc} ON {ct} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {fn}();", ""]
for ab in ABSTRACT:
    subs = [c for c, p in PARENT.items() if p == ab]
    at = table_name(ab); fn = f"chk_{at}_has_subtype"
    cases = "\n".join(f"    WHEN '{upper_snake(s)}' THEN PERFORM 1 FROM {table_name(s)} WHERE {pk_col(s)} = NEW.id;" for s in subs)
    out += [f"-- Abstract class {ab}: each row must have its subtype row", f"CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$", "BEGIN",
            f"  CASE NEW.{snake(ab)}_type", cases, "  END CASE;",
            f"  IF NOT FOUND THEN RAISE EXCEPTION 'Abstract class {ab}: id % has no subtype row', NEW.id; END IF;",
            "  RETURN NULL;", "END $$;",
            f"CREATE CONSTRAINT TRIGGER {fn}_t AFTER INSERT ON {at} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {fn}();", ""]
out += ["COMMIT;", ""]
SQL = OUT / f"02_sql_ekte-mat-schema_postgresql_{DATE}.sql"
SQL.write_text("\n".join(out), encoding="utf-8")

# --------------------------------------------------------------- optional live tests
TESTS = [
 ("T01", "Valid private customer with an order, guest group, line, menu and dish", True, """
INSERT INTO customer (id, customer_type, name, created_at) OVERRIDING SYSTEM VALUE VALUES (1,'PRIVATE_CUSTOMER','Test person',now());
INSERT INTO private_customer (customer_id) VALUES (1);
INSERT INTO menu (id, season, valid_from, published) OVERRIDING SYSTEM VALUE VALUES (1,'Autumn 2026','2026-09-01',true);
INSERT INTO dish (id, name_no, name_en, price_per_person_nok) OVERRIDING SYSTEM VALUE VALUES (1,'Fiskesuppe','Fish soup',189);
INSERT INTO menu_dish VALUES (1,1);
INSERT INTO allergen (id, code, name_no, name_en) OVERRIDING SYSTEM VALUE VALUES (1,'FISH','Fisk','Fish');
INSERT INTO dish_allergen VALUES (1,1);
INSERT INTO customer_order (id, order_number, event_type, event_date, status, channel, delivery_method, created_at, customer_id)
  OVERRIDING SYSTEM VALUE VALUES (1,'26-0001','PARTY','2026-12-12','REQUESTED','ONLINE','PICK_UP',now(),1);
INSERT INTO guest_group (guest_count, customer_order_id) VALUES (30, 1);
INSERT INTO order_line (quantity, customer_order_id, dish_id) VALUES (30, 1, 1);
SELECT setval(pg_get_serial_sequence(t, 'id'), 1000) FROM unnest(ARRAY['customer','menu','dish','allergen','customer_order']) t;"""),
 ("T02", "Order without any guest group (Order 1 *-- 1..* GuestGroup)", False, """
INSERT INTO customer_order (order_number, event_type, event_date, status, channel, delivery_method, created_at, customer_id)
  VALUES ('26-0002','PARTY','2026-12-13','REQUESTED','ONLINE','PICK_UP',now(),1);"""),
 ("T03", "Corporate subtype row for a PRIVATE customer (inheritance discriminator)", False, """
INSERT INTO corporate_customer (customer_id, organisation_number, monthly_invoicing) VALUES (1,'999999999',true);"""),
 ("T04", "Guest group with guestCount 0 ({>0})", False, "UPDATE guest_group SET guest_count = 0;"),
 ("T05", "Second invoice line for the same order (InvoiceLine 0..1 -- 1 Order)", False, """
INSERT INTO invoice (id, invoice_number, format, status, customer_id) OVERRIDING SYSTEM VALUE VALUES (1,'INV-1','PDF','DRAFT',1);
INSERT INTO invoice_line (description, amount_nok, invoice_id, customer_order_id) VALUES ('a',100,1,1),('b',100,1,1);"""),
 ("T06", "Delete a customer who has orders (RESTRICT)", False, "DELETE FROM customer WHERE id = 1;"),
 ("T07", "Second allergy confirmation for the same order (1 -- 0..1)", False, """
INSERT INTO staff_user (id, name, role) OVERRIDING SYSTEM VALUE VALUES (1,'Chef','HEAD_CHEF');
INSERT INTO allergy_confirmation (confirmed_at, customer_order_id, staff_user_id) VALUES (now(),1,1),(now(),1,1);"""),
 ("T08", "Delete an allergen that a dish uses (junction RESTRICT)", False, "DELETE FROM allergen WHERE id = 1;"),
 ("T09", "Customer row without subtype row (abstract Customer)", False,
  "INSERT INTO customer (customer_type, name, created_at) VALUES ('PRIVATE_CUSTOMER','No subtype',now());"),
 ("T10", "Menu without dishes (Menu 0..* -- 1..* Dish)", False,
  "INSERT INTO menu (season, valid_from, published) VALUES ('Empty','2026-12-01',false);"),
 ("T11", "Deleting an order removes its guest groups and lines (composition CASCADE)", True, """
DELETE FROM customer_order WHERE id = 1;
DO $$ BEGIN IF (SELECT count(*) FROM guest_group) + (SELECT count(*) FROM order_line) <> 0 THEN RAISE EXCEPTION 'parts left'; END IF; END $$;"""),
]
# A rejected test only passes if the database gives the expected reason.
EXPECT_ERR = {"T02": "Multiplicity violated: Order must have at least 1", "T03": "violates foreign key constraint",
  "T04": "violates check constraint", "T05": "duplicate key value", "T06": "violates foreign key constraint",
  "T07": "duplicate key value", "T08": "violates foreign key constraint", "T09": "has no subtype row",
  "T10": "Multiplicity violated: Menu must have at least 1 Dish"}
results = []
if "--test" in sys.argv:
    psql = sys.argv[sys.argv.index("--test") + 1].split()
    def run(sql):
        p = subprocess.run(psql + ["-v", "ON_ERROR_STOP=1", "-q", "-X"], input=sql, text=True, capture_output=True)
        errs = [l for l in p.stderr.splitlines() if l.startswith("ERROR") or ":ERROR" in l or "ERROR:" in l]
        return p.returncode == 0, (errs[0] if errs else p.stderr.strip())
    ok, err = run(SQL.read_text())
    results.append(("DDL", "Generated schema executes", True, ok, "" if ok else err, True))
    for tid, desc, expect, sql in TESTS:
        ok, err = run(f"BEGIN;\n{sql}\nCOMMIT;\n")
        msg = "" if ok else re.sub(r"^.*?ERROR:\s*", "", err)
        reason_ok = ok or (tid in EXPECT_ERR and EXPECT_ERR[tid] in msg)
        results.append((tid, desc, expect, ok, msg, reason_ok))

# --------------------------------------------------------------- reports
def mdtable(head, rows):
    esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
rep = [f"# UML consistency check ({DATE})", "",
 "Models checked: `02_uml_use-case`, `02_uml_domain-class`, `02_uml_sequence_standing-order-ehf-invoice`, `02_uml_state-machine_order` "
 f"(all dated {DATE}) against the Must/Should stories in `01_Requirements/EkteMat_backlog_v1.xlsx`.",
 f"Generated by `02_uml_check-and-ddl_{DATE}.py`, which parses the .puml files themselves.", "",
 "## Rules", ""] + mdtable(["Rule", "Check"], RULES.items()) + ["", "## Result per rule", ""]
cnt = collections.Counter(v[0] for v in V)
rep += mdtable(["Rule", "Elements checked", "Violations"], [
 ("R1", f"{len(USECASES)} use cases", cnt["R1"]), ("R2", f"{len(MS)} Must/Should stories", cnt["R2"]),
 ("R3", f"{len(part_class)} class participants of {len(SEQ_PART)} participants", cnt["R3"]),
 ("R4", f"{len(SM_STATES)} states / {len(status_vals)} OrderStatus values", cnt["R4"]),
 ("R5", f"{len(SEQ_MSG)} sequence messages", cnt["R5"]), ("R6", "sequence assignments and story citations", cnt["R6"])])
rep += ["", "## Violations", ""]
rep += mdtable(["#", "Rule", "Diagram", "Element", "Problem", "Suggested fix"], [(i, *v) for i, v in enumerate(V, 1)]) if V else ["No violations."]
rep += ["", "### How to read the remaining violations", "",
 "- **US-13 (Could) on the Cancelled transitions:** the Cancelled state was requested by the assignment, but only US-13 (Could) supports it and its terms are missing (ISS-04). The violation is kept visible on purpose; the product owner should decide whether to raise US-13 to Should or drop the state.", "",
 "## History of this check", "",
 "- **First run, " + DATE + ":** R6 also reported `period is not an attribute of Invoice` in the month-end `<<create>>` message.",
 "  - Fix: the sequence diagram now uses `periodStart` and `periodEnd`, which exist in the class diagram.",
 "- **Self-test of the checker:** run on a deliberately broken copy of the models, it detected all injected faults:",
 "  - a use case with no story (R1);",
 "  - a story that is not Must/Should (R1);",
 "  - the resulting coverage gaps (R2);",
 "  - an unknown class `:Delivery` (R3);",
 "  - a renamed OrderStatus value (R4).", "",
 "## Traceability: use case -> user stories", ""]
rep += mdtable(["Use case", "Stories", "Priority"], [(l.split("\\n")[0], ", ".join(re.findall(r"US-\d\d", l)),
        ", ".join(STORY[i][0] for i in re.findall(r"US-\d\d", l) if i in STORY)) for _, l in USECASES])
rep += ["", "## Sequence participants", ""]
rep += mdtable(["Participant", "Kind", "Domain class", "In class diagram"],
        [(p["label"], p["kind"], part_class.get(p["alias"], "- (not a domain object)"),
          ("yes" if part_class.get(p["alias"]) in CLASSES else "NO") if p["alias"] in part_class else "n/a") for p in SEQ_PART])
(OUT / f"02_uml_consistency-report_{DATE}.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

mp = [f"# SQL DDL mapping decisions ({DATE})", "",
 f"Model-driven step: `02_sql_ekte-mat-schema_postgresql_{DATE}.sql` is generated from `02_uml_domain-class_{DATE}.puml` "
 f"by `02_uml_check-and-ddl_{DATE}.py`. Each row below is logged by the generator when it applies a rule.", "",
 "## General rules", "",
 "1. **Class -> table.** Names become snake_case. `Order` becomes `customer_order` because ORDER is a reserved SQL word.",
 "2. **Identity.** Each table gets a surrogate key `id BIGINT GENERATED ALWAYS AS IDENTITY`. Business keys marked `{unique}` (orderNumber, invoiceNumber, ...) become UNIQUE columns.",
 "3. **Attribute multiplicity.** `[1]` becomes NOT NULL; `[0..1]` becomes a nullable column.",
 "4. **Types.** String -> TEXT, Integer -> INTEGER, Boolean -> BOOLEAN, Date -> DATE, DateTime -> TIMESTAMPTZ (time zone safe), Time -> TIME, Money -> NUMERIC(12,2) in NOK (exact; never FLOAT for money).",
 "5. **Enumerations** become PostgreSQL ENUM types, so only the modelled values can be stored.",
 "6. **Constraints.** `{>0}` and `{>=0}` become CHECK constraints.",
 "7. **Association with upper bound 1 on one end (1 or 0..1 to many).** The FK goes in the table on the many end. A lower bound of 1 on the one end gives NOT NULL; 0 gives a nullable FK.",
 "8. **One-to-one (1 to 0..1).** The FK goes in the optional side and gets UNIQUE, so the mandatory side can have at most one partner.",
 "9. **Many-to-many** becomes a junction table with a composite primary key, which also prevents duplicate links.",
 "10. **Delete behaviour:**",
 "    - Composition (filled diamond) -> ON DELETE CASCADE, because the parts cannot exist without the whole.",
 "    - Optional link -> SET NULL.",
 "    - Mandatory reference -> RESTRICT, so data still in use cannot be removed.",
 "    - Junction tables: CASCADE from the owning (left) class and RESTRICT from the referenced class, e.g. an allergen still labelling a dish cannot be deleted.",
 "11. **Lower bound 1 on a many end (1..\\*)** cannot be expressed with foreign keys. It is enforced by a DEFERRABLE INITIALLY DEFERRED constraint trigger, checked at COMMIT so the parent and its first child can be inserted in the same transaction.",
 "12. **Generalisation** uses class-table inheritance:",
 "    - The parent table holds the shared attributes plus a discriminator (`customer_type`).",
 "    - Each subclass table uses the parent's id as its primary key and foreign key.",
 "    - A composite FK (id, type) ensures a subtype row matches the parent's type.",
 "    - The abstract parent gets a deferred trigger so every customer has its subtype row.",
 "    - Chosen over single-table inheritance (many nullable subtype columns) and concrete-table inheritance (Order could not reference one customer table).",
 "13. **Indexes.** PostgreSQL does not index FK columns automatically, so each FK gets an index (except where UNIQUE or the PK already provides one).", "",
 "## Decision log (every element)", ""]
mp += mdtable(["#", "Model element", "Mapping rule applied", "SQL result"], [(i, *d) for i, d in enumerate(DEC, 1)])
mp += ["", "## Not mapped / limitations", "",
 "- **CapacityLimit** is a standalone table; whether limits block or warn is unresolved (ISS-06).",
 "- **Personal-data deletion (US-31):** RESTRICT on `customer` means a customer with orders cannot be deleted. Deletion must anonymise personal fields instead, because bookkeeping data is kept for 5 years (GDPR note). This is a design decision for the PO, not modelled in the class diagram.",
 "- **State transitions:** the database stores `status` but does not enforce the allowed transitions from the state machine; that belongs in application logic or a trigger in a later iteration.", ""]
if results:
    mp += ["## Live test against PostgreSQL", ""]
    mp += ["Each test runs in its own transaction against the generated schema. A rejection only counts as a pass when the error is the expected one.", ""]
    mp += mdtable(["Test", "Description", "Expected", "Actual", "Pass", "Database message"],
                  [(t, d, "accepted" if e else "rejected", "accepted" if a else "rejected", "yes" if e == a and r else "NO", m) for t, d, e, a, m, r in results])
(OUT / f"02_sql_mapping-decisions_{DATE}.md").write_text("\n".join(mp) + "\n", encoding="utf-8")

print(json.dumps({"use_cases": len(USECASES), "classes": len(CLASSES), "enums": len(ENUMS), "associations": len(ASSOC),
                  "tables": len(TABLES), "decisions": len(DEC), "violations": [list(v) for v in V],
                  "tests": [(t, e == a and r, m) for t, d, e, a, m, r in results]}, indent=1))
