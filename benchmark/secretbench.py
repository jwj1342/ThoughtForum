"""SecretBench: projects whose methods depend on private record formats that cannot be guessed.

ClassEval interfaces can mostly be inferred from method names and the caller's own docstring,
so even with hidden docstrings (spec=private) a text forum added little there (E0p). Here every
project is a class that stores records of one entity in two private formats:

- producers: `encode(<fields>)` writes the primary record format, `export(<fields>)` the export
  format. Only their docstrings state the formats.
- consumers: `decode`, `is_record` and `get_field` read primary records, `read_export` reads export
  records, and `migrate` turns a primary record into an export record, so it needs both formats,
  that is, the posts of two producers.

Consumer docstrings and visible tests do not depend on the formats, so under spec=private a
consumer learns a format only from the forum (or by calling a producer at run time and inferring
it; the isolated evaluation uses the reference producers). Under spec=full everyone sees the
formats: the upper bound.

The primary format: a tag of `tag_len` capital letters, a delimiter, an order of the fields that
differs from the signature, integers zero-padded to a fixed width, and on some projects a two-digit
checksum (sum of the character codes of the rest of the record, mod 97) as the last part. The export
format: another tag and delimiter, and `field<sep>value` pairs in yet another order. `meta["bits"]`
gives the information in each format. Class name, entity, fields (3 to 5), values and formats are
drawn per (seed, index); the first len(ENTITIES) * len(SUFFIXES) indices have distinct class names.
"""
from __future__ import annotations

import itertools
import math
import random

from benchmark.tasks import Project, Subtask, _first_test_only

# entity, record noun, fields as (name, kind); kinds draw values from the pools below
ENTITIES = [
    ("Book", "book", [("title", "word"), ("author", "name"), ("year", "int"), ("pages", "int"), ("publisher", "word")]),
    ("Order", "order", [("order_id", "code"), ("item", "word"), ("qty", "int"), ("price", "int"), ("buyer", "name")]),
    ("Sensor", "reading", [("sensor", "code"), ("site", "city"), ("value", "int"), ("battery", "int"), ("unit", "word")]),
    ("Ticket", "ticket", [("ticket_id", "code"), ("owner", "name"), ("priority", "int"), ("queue", "word"), ("age_days", "int")]),
    ("Flight", "flight", [("flight", "code"), ("origin", "city"), ("gate", "code"), ("delay", "int"), ("seats", "int")]),
    ("Patient", "visit", [("patient", "code"), ("ward", "word"), ("bed", "int"), ("doctor", "name"), ("age", "int")]),
    ("Parcel", "parcel", [("tracking", "code"), ("city", "city"), ("weight", "int"), ("courier", "name"), ("zone", "int")]),
    ("Course", "enrollment", [("student", "name"), ("course", "code"), ("grade", "int"), ("credits", "int"), ("term", "word")]),
    ("Invoice", "invoice", [("invoice", "code"), ("client", "name"), ("amount", "int"), ("due_day", "int"), ("currency", "word")]),
    ("Vehicle", "vehicle", [("plate", "code"), ("make", "word"), ("year", "int"), ("mileage", "int"), ("owner", "name")]),
    ("Staff", "employee", [("emp_id", "code"), ("person", "name"), ("dept", "word"), ("salary", "int"), ("floor", "int")]),
    ("Recipe", "recipe", [("dish", "word"), ("chef", "name"), ("minutes", "int"), ("servings", "int"), ("cuisine", "word")]),
    ("Match", "match", [("home", "city"), ("away", "city"), ("home_goals", "int"), ("away_goals", "int"), ("referee", "name")]),
    ("Song", "song", [("song", "word"), ("artist", "name"), ("seconds", "int"), ("bpm", "int"), ("album", "word")]),
    ("Room", "room", [("room", "code"), ("building", "word"), ("capacity", "int"), ("floor", "int"), ("manager", "name")]),
    ("Loan", "loan", [("loan_id", "code"), ("borrower", "name"), ("principal", "int"), ("months", "int"), ("branch", "city")]),
    ("Cargo", "shipment", [("container", "code"), ("port", "city"), ("tons", "int"), ("vessel", "word"), ("berth", "int")]),
    ("Exam", "result", [("candidate", "name"), ("subject", "word"), ("score", "int"), ("rank", "int"), ("center", "city")]),
    ("Server", "server", [("host", "code"), ("region", "city"), ("cores", "int"), ("ram_gb", "int"), ("role", "word")]),
    ("Hotel", "booking", [("guest", "name"), ("hotel", "word"), ("nights", "int"), ("room_no", "int"), ("city", "city")]),
    ("Zoo", "animal", [("chip", "code"), ("species", "word"), ("age", "int"), ("weight", "int"), ("keeper", "name")]),
    ("Garden", "plant", [("plot", "code"), ("species", "word"), ("height", "int"), ("age", "int"), ("gardener", "name")]),
    ("Device", "device", [("serial", "code"), ("model", "word"), ("firmware", "int"), ("port", "int"), ("owner", "name")]),
    ("Account", "account", [("account", "code"), ("holder", "name"), ("balance", "int"), ("branch", "city"), ("tier", "int")]),
    ("Article", "article", [("slug", "word"), ("writer", "name"), ("words", "int"), ("views", "int"), ("section", "word")]),
    ("Race", "result", [("runner", "name"), ("event", "word"), ("seconds", "int"), ("bib", "int"), ("club", "city")]),
    ("Repair", "job", [("job", "code"), ("technician", "name"), ("hours", "int"), ("cost", "int"), ("part", "word")]),
    ("Assay", "sample", [("sample", "code"), ("assay", "word"), ("value", "int"), ("plate", "int"), ("analyst", "name")]),
    ("Lease", "lease", [("unit", "code"), ("tenant", "name"), ("rent", "int"), ("months", "int"), ("city", "city")]),
    ("Grant", "grant", [("grant", "code"), ("lead", "name"), ("budget", "int"), ("year", "int"), ("field", "word")]),
    ("Trip", "trip", [("driver", "name"), ("origin", "city"), ("destination", "city"), ("km", "int"), ("fare", "int")]),
    ("Batch", "batch", [("batch", "code"), ("product", "word"), ("units", "int"), ("line", "int"), ("inspector", "name")]),
    ("Claim", "claim", [("claim", "code"), ("insured", "name"), ("amount", "int"), ("days", "int"), ("kind", "word")]),
    ("Concert", "show", [("venue", "word"), ("artist", "name"), ("tickets", "int"), ("price", "int"), ("city", "city")]),
    ("Permit", "permit", [("permit", "code"), ("applicant", "name"), ("fee", "int"), ("year", "int"), ("district", "city")]),
    ("Turbine", "turbine", [("turbine", "code"), ("farm", "city"), ("kw", "int"), ("rpm", "int"), ("vendor", "word")]),
    ("Volunteer", "volunteer", [("person", "name"), ("project", "word"), ("hours", "int"), ("shifts", "int"), ("city", "city")]),
    ("Delivery", "delivery", [("drop", "code"), ("recipient", "name"), ("boxes", "int"), ("floor", "int"), ("street", "word")]),
    ("Meter", "reading", [("meter", "code"), ("household", "name"), ("kwh", "int"), ("month", "int"), ("feeder", "word")]),
    ("Clinic", "pet", [("pet", "word"), ("owner", "name"), ("age", "int"), ("weight", "int"), ("vet", "name")]),
]
SUFFIXES = ["Catalog", "Registry", "Ledger", "Archive", "Index", "Tracker", "Store", "Board"]
POOLS = {
    "name": ["maya", "omar", "li", "ana", "ben", "cyrus", "dara", "eli", "fatima", "goran", "hana", "ivan", "jun",
             "kofi", "lena", "mateo", "nia", "oskar", "priya", "quinn", "rosa", "sami", "tara", "uma", "viktor", "wen"],
    "word": ["amber", "basil", "cedar", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper", "kelp",
             "lumen", "maple", "nectar", "onyx", "pebble", "quartz", "raven", "sable", "tundra", "velvet", "willow"],
    "city": ["Oslo", "Lima", "Pune", "Accra", "Kyoto", "Quito", "Riga", "Turin", "Hanoi", "Perth", "Cairo", "Lagos",
             "Porto", "Seoul", "Tunis", "Dakar"],
}
DELIMS = ["|", ";", "#", "~", "^", "!", "/", "+"]
SEPS = ["=", ":"]
WIDTHS = [4, 5, 6]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PRODUCERS = ("encode", "export")
CONSUMERS = {"decode": ["encode"], "is_record": ["encode"], "get_field": ["encode"],
             "read_export": ["export"], "migrate": ["encode", "export"]}


def checksum(body: str) -> str:
    return f"{sum(map(ord, body)) % 97:02d}"


def primary(fmt: dict, values: dict) -> str:
    """A record in the primary format."""
    parts = [fmt["tag"]] + [f"{values[f]:0{fmt['width']}d}" if isinstance(values[f], int) else values[f]
                            for f in fmt["order"]]
    body = fmt["delim"].join(parts)
    return body + fmt["delim"] + checksum(body) if fmt["checksum"] else body


def exported(fmt: dict, values: dict) -> str:
    """A record in the export format."""
    return fmt["delim"].join([fmt["tag"]] + [f"{f}{fmt['sep']}{values[f]}" for f in fmt["order"]])


def format_bits(fmt: dict, n_fields: int) -> float:
    orders = math.factorial(n_fields) - (1 if "width" in fmt else 2)
    choices = len(LETTERS) ** len(fmt["tag"]) * len(DELIMS) * orders
    choices *= len(WIDTHS) * 2 if "width" in fmt else len(SEPS)
    return round(math.log2(choices), 1)


def describe(fmt: dict, kind: str) -> str:
    """The format in words, as the producer's docstring states it."""
    if kind == "encode":
        s = (f"the tag '{fmt['tag']}', then the fields {', '.join(fmt['order'])} (in that order), all joined by "
             f"'{fmt['delim']}'; integers are zero-padded to {fmt['width']} digits")
        return s + (", and a last part holds a two-digit checksum: the sum of the character codes of everything "
                    "before that last delimiter, mod 97" if fmt["checksum"] else "")
    return (f"the tag '{fmt['tag']}', then one '<field>{fmt['sep']}<value>' pair per field in the order "
            f"{', '.join(fmt['order'])}, all joined by '{fmt['delim']}'")


def project_id(i: int, seed: int = 0, tag_len: int = 4) -> str:
    return f"Secret_{seed}_{i}" if tag_len == 4 else f"Secret{tag_len}_{seed}_{i}"


def _value(rng, kind):
    if kind == "int":
        return rng.randint(1, 999)
    if kind == "code":
        return rng.choice(LETTERS) + str(rng.randint(10, 999))
    return rng.choice(POOLS[kind])


def _formats(rng, fields, ints, tag_len):
    tag = lambda: "".join(rng.choice(LETTERS) for _ in range(tag_len))
    orders = [list(p) for p in itertools.permutations(fields) if list(p) != fields]
    a = {"tag": tag(), "delim": rng.choice(DELIMS), "order": rng.choice(orders), "width": rng.choice(WIDTHS),
         "checksum": rng.random() < 0.5}
    b = {"tag": tag(), "delim": rng.choice([d for d in DELIMS if d != a["delim"]]), "sep": rng.choice(SEPS),
         "order": rng.choice([o for o in orders if o != a["order"]])}
    while b["tag"] == a["tag"]:
        b["tag"] = tag()
    return a, b


def make_project(i: int, seed: int = 0, tag_len: int = 4) -> Project:
    rng = random.Random(f"secretbench-{seed}-{i}")
    entity, rec, pool = ENTITIES[i % len(ENTITIES)]
    cls = entity + SUFFIXES[(i // len(ENTITIES)) % len(SUFFIXES)]
    n = rng.choice([3, 4, 5])
    keep = sorted(rng.sample(range(len(pool)), n))
    if not any(pool[k][1] == "int" for k in keep):   # every project has an integer field (the padding matters)
        keep[-1] = next(k for k, (_, kind) in enumerate(pool) if kind == "int" and k not in keep)
        keep.sort()
    fields = [pool[k][0] for k in keep]
    kinds = {pool[k][0]: pool[k][1] for k in keep}
    ints = [f for f in fields if kinds[f] == "int"]
    A, B = _formats(rng, fields, ints, tag_len)
    samples = [{f: _value(rng, kinds[f]) for f in fields} for _ in range(3)]
    sig = ", ".join(fields)
    call = lambda v: ", ".join(repr(v[f]) for f in fields)
    rA = [primary(A, v) for v in samples]
    rB = [exported(B, v) for v in samples]
    other_tag = "".join(LETTERS[(LETTERS.index(c) + 7) % 26] for c in A["tag"])
    other_btag = "".join(LETTERS[(LETTERS.index(c) + 7) % 26] for c in B["tag"])
    types = (f"{', '.join(repr(f) for f in ints)} {'are ints' if len(ints) > 1 else 'is an int'}; "
             f"the other values are strings")
    keys = ", ".join(repr(f) for f in fields)

    docs = {
        "encode": f'''    def encode(self, {sig}):
        """
        Encode one {rec} as a string in this project's record format.
        Format: {describe(A, "encode")}.
        :return: str
        >>> c = {cls}()
        >>> c.encode({call(samples[0])})
        {rA[0]!r}
        """''',
        "export": f'''    def export(self, {sig}):
        """
        Encode one {rec} in this project's export format.
        Format: {describe(B, "export")}.
        :return: str
        >>> c = {cls}()
        >>> c.export({call(samples[0])})
        {rB[0]!r}
        """''',
        "decode": f'''    def decode(self, s):
        """
        Decode a record string produced by `encode` into a dict with the keys {keys}.
        {types}. Raise ValueError if s is not a valid record.
        :return: dict
        >>> c = {cls}()
        >>> c.decode(c.encode({call(samples[0])})) == {samples[0]!r}
        True
        """''',
        "is_record": f'''    def is_record(self, s):
        """
        Check whether s is a valid record string exactly as `encode` writes it.
        :return: bool
        >>> c = {cls}()
        >>> c.is_record('')
        False
        """''',
        "get_field": f'''    def get_field(self, s, name):
        """
        Return the value of the field `name` (one of {keys}) of the record string s,
        as `decode` would. Raise KeyError if name is not one of these fields.
        >>> c = {cls}()
        >>> c.get_field(c.encode({call(samples[0])}), {fields[1]!r})
        {samples[0][fields[1]]!r}
        """''',
        "read_export": f'''    def read_export(self, t):
        """
        Read a string produced by `export` back into a dict with the keys {keys}.
        {types}. Raise ValueError if t is not an export string.
        :return: dict
        >>> c = {cls}()
        >>> c.read_export(c.export({call(samples[0])})) == {samples[0]!r}
        True
        """''',
        "migrate": f'''    def migrate(self, s):
        """
        Convert a record string produced by `encode` into the export string that `export` would
        produce for the same {rec}. Raise ValueError if s is not a valid record.
        :return: str
        >>> c = {cls}()
        >>> c.migrate(c.encode({call(samples[0])})) == c.export({call(samples[0])})
        True
        """''',
    }

    # the reference consumers share one parser for primary records
    parse = [f"parts = s.split({A['delim']!r}) if isinstance(s, str) else []"]
    if A["checksum"]:
        parse += [f"body, _, check = s.rpartition({A['delim']!r}) if isinstance(s, str) else ('', '', '')",
                  "if not check.isdigit() or sum(map(ord, body)) % 97 != int(check):",
                  "    raise ValueError('bad checksum')",
                  f"parts = body.split({A['delim']!r})"]
    parse += [f"if len(parts) != {len(fields) + 1} or parts[0] != {A['tag']!r}:",
              "    raise ValueError('not a record')",
              f"v = {{f: int(x) if f in {ints!r} else x for f, x in zip({A['order']!r}, parts[1:])}}"]
    width = [f"for f, x in zip({A['order']!r}, parts[1:]):",
             f"    if f in {ints!r} and len(x) != {A['width']}:",
             "        raise ValueError('bad width')"]
    block = lambda lines, depth=2: "\n".join("    " * depth + line for line in lines) + "\n"
    to_export = f"{B['delim']!r}.join([{B['tag']!r}] + [f + {B['sep']!r} + str(v[f]) for f in {B['order']!r}])"
    sols = {
        "encode": f"    def encode(self, {sig}):\n" + block([
            f"v = {{{', '.join(f'{f!r}: {f}' for f in fields)}}}",
            f"parts = [{A['tag']!r}] + [f'{{v[f]:0{A['width']}d}}' if isinstance(v[f], int) else str(v[f]) "
            f"for f in {A['order']!r}]",
            f"body = {A['delim']!r}.join(parts)",
            (f"return body + {A['delim']!r} + f'{{sum(map(ord, body)) % 97:02d}}'" if A["checksum"] else "return body")]),
        "export": f"    def export(self, {sig}):\n" + block([
            f"v = {{{', '.join(f'{f!r}: {f}' for f in fields)}}}", f"return {to_export}"]),
        "decode": "    def decode(self, s):\n" + block(parse + ["return v"]),
        "is_record": "    def is_record(self, s):\n        try:\n" + block(parse + width, 3)
                     + "        except ValueError:\n            return False\n        return True\n",
        "get_field": "    def get_field(self, s, name):\n" + block([
            f"if name not in {fields!r}:", "    raise KeyError(name)",
            f"x = s.split({A['delim']!r})[{A['order']!r}.index(name) + 1]",
            f"return int(x) if name in {ints!r} else x"]),
        "read_export": "    def read_export(self, t):\n" + block([
            f"parts = t.split({B['delim']!r}) if isinstance(t, str) else []",
            f"if len(parts) != {len(fields) + 1} or parts[0] != {B['tag']!r}:",
            "    raise ValueError('not an export string')",
            f"out = dict(p.split({B['sep']!r}, 1) for p in parts[1:])",
            f"return {{f: int(out[f]) if f in {ints!r} else out[f] for f in {fields!r}}}"]),
        "migrate": "    def migrate(self, s):\n" + block(parse + [f"return {to_export}"]),
    }

    T, C = f"{cls}Test", f"{cls}()"
    bad_check = rA[1][:-2] + f"{(int(rA[1][-2:]) + 1) % 97:02d}" if A["checksum"] else None
    wide = primary(dict(A, width=A["width"] + 1), samples[2])
    tests = {
        "encode": f'''class {T}Encode(unittest.TestCase):
''' + "".join(f'''    def test_encode_{k + 1}(self):
        self.assertEqual({C}.encode({call(samples[k])}), {rA[k]!r})

''' for k in range(3)),
        "export": f'''class {T}Export(unittest.TestCase):
''' + "".join(f'''    def test_export_{k + 1}(self):
        self.assertEqual({C}.export({call(samples[k])}), {rB[k]!r})

''' for k in range(3)),
        # the first test of each consumer is its visible test, and it does not depend on the formats
        "decode": f'''class {T}Decode(unittest.TestCase):
    def test_decode_1(self):
        with self.assertRaises(ValueError):
            {C}.decode('')

    def test_decode_2(self):
        self.assertEqual({C}.decode({rA[0]!r}), {samples[0]!r})

    def test_decode_3(self):
        self.assertEqual({C}.decode({rA[1]!r}), {samples[1]!r})

    def test_decode_4(self):
        with self.assertRaises(ValueError):
            {C}.decode({rA[0].replace(A['tag'], other_tag, 1)!r})
''' + (f'''
    def test_decode_5(self):
        with self.assertRaises(ValueError):
            {C}.decode({bad_check!r})
''' if bad_check else ""),
        "is_record": f'''class {T}IsRecord(unittest.TestCase):
    def test_is_record_1(self):
        self.assertFalse({C}.is_record(''))

    def test_is_record_2(self):
        self.assertTrue({C}.is_record({rA[1]!r}))

    def test_is_record_3(self):
        self.assertTrue({C}.is_record({rA[2]!r}))

    def test_is_record_4(self):
        self.assertFalse({C}.is_record({rA[1].replace(A['tag'], other_tag, 1)!r}))

    def test_is_record_5(self):
        self.assertFalse({C}.is_record({A['delim'].join(rA[2].split(A['delim'])[:-1])!r}))

    def test_is_record_6(self):
        self.assertFalse({C}.is_record({wide!r}))
''' + (f'''
    def test_is_record_7(self):
        self.assertFalse({C}.is_record({bad_check!r}))
''' if bad_check else ""),
        "get_field": f'''class {T}GetField(unittest.TestCase):
    def test_get_field_1(self):
        with self.assertRaises(KeyError):
            {C}.get_field('', 'no_such_field')
''' + "".join(f'''
    def test_get_field_{k + 2}(self):
        self.assertEqual({C}.get_field({rA[k % 3]!r}, {f!r}), {samples[k % 3][f]!r})
''' for k, f in enumerate(fields[:3])),
        "read_export": f'''class {T}ReadExport(unittest.TestCase):
    def test_read_export_1(self):
        with self.assertRaises(ValueError):
            {C}.read_export('')

    def test_read_export_2(self):
        self.assertEqual({C}.read_export({rB[0]!r}), {samples[0]!r})

    def test_read_export_3(self):
        self.assertEqual({C}.read_export({rB[2]!r}), {samples[2]!r})

    def test_read_export_4(self):
        with self.assertRaises(ValueError):
            {C}.read_export({rB[1].replace(B['tag'], other_btag, 1)!r})
''',
        "migrate": f'''class {T}Migrate(unittest.TestCase):
    def test_migrate_1(self):
        with self.assertRaises(ValueError):
            {C}.migrate('')

    def test_migrate_2(self):
        self.assertEqual({C}.migrate({rA[0]!r}), {rB[0]!r})

    def test_migrate_3(self):
        self.assertEqual({C}.migrate({rA[2]!r}), {rB[2]!r})
''',
    }
    skeleton = (f'class {cls}:\n    """\n    Stores {rec}s as strings in two project-specific formats: records and exports.\n    """\n\n'
                f'    def __init__(self):\n        pass\n\n' + "\n\n".join(docs.values()) + "\n")
    deps = {"encode": [], "export": [], **CONSUMERS}
    # consumers depend on the producers' formats but may not call them (or each other): a consumer that
    # delegated to reference code, or called `encode` to infer its format, would pass without knowing it
    subtasks = [Subtask(name=k, doc=docs[k].strip(), deps=deps[k], visible_test=_first_test_only(tests[k]),
                        hidden_test=tests[k], solution=sols[k], calls=[]) for k in docs]
    return Project(pid=project_id(i, seed, tag_len), class_name=cls, skeleton=skeleton, subtasks=subtasks,
                   meta={"benchmark": "secretbench", "record": rec, "fields": fields, "ints": ints,
                         "samples": samples, "formats": {"encode": A, "export": B},
                         "bits": {"encode": format_bits(A, len(fields)), "export": format_bits(B, len(fields))}})
