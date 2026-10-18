"""SecretBench: projects where some information cannot be guessed and has to be communicated.

ClassEval interfaces can mostly be inferred from method names and the caller's own docstring,
so even with hidden docstrings (spec=private) a text forum added nothing (E0p). Here every
project has one producer and three consumers:

- encode(f1, f2, f3): writes a record in a private format: a random 4-letter tag, a delimiter,
  and a field order that differs from the signature order. Only its docstring states the format.
- decode(s), is_record(s), get_field(s, name): read such records. Their docstrings and their
  visible tests do not depend on the format, so neither the spec nor CI leaks it.

Under spec=private, a consumer can only learn the format from the forum (or by calling encode at
run time and inferring it, which is allowed; the isolated evaluation uses the reference encode).
Under spec=full, everyone sees the format: that is the upper bound. The format carries about
log2(26^4 * 6 * 5) ~ 23 bits; the three consumers need different parts of it.
"""
from __future__ import annotations

import itertools
import random

from benchmark.tasks import Project, Subtask, _first_test_only

DOMAINS = [
    ("BookCatalog", "book", ["title", "author", "year"], [("Dune", "Herbert", 1965), ("Emma", "Austen", 1815), ("Ulysses", "Joyce", 1922)]),
    ("OrderLog", "order", ["order_id", "item", "qty"], [("A17", "lamp", 2), ("B09", "desk", 1), ("C33", "chair", 4)]),
    ("SensorFeed", "reading", ["sensor", "unit", "value"], [("t1", "C", 21.5), ("p4", "kPa", 101), ("h2", "pct", 40)]),
    ("TicketDesk", "ticket", ["ticket_id", "owner", "priority"], [("T100", "maya", "high"), ("T101", "omar", "low"), ("T102", "li", "mid")]),
    ("FlightBoard", "flight", ["code", "origin", "gate"], [("AC12", "YYZ", "B7"), ("LH40", "FRA", "A2"), ("NH9", "HND", "C11")]),
    ("PatientChart", "visit", ["patient", "ward", "bed"], [("P12", "cardio", 3), ("P40", "neuro", 11), ("P77", "ortho", 5)]),
    ("ParcelTracker", "parcel", ["tracking", "city", "weight"], [("Z991", "Oslo", 2.5), ("Z104", "Lima", 7), ("Z377", "Pune", 1.2)]),
    ("CourseRoster", "enrollment", ["student", "course", "grade"], [("ana", "CS101", "A"), ("ben", "MA201", "B"), ("cy", "PH110", "C")]),
]
DELIMS = ["|", ";", "#", "~", "^", "!"]


def _secret(rng, fields):
    tag = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(4))
    delim = rng.choice(DELIMS)
    orders = [list(p) for p in itertools.permutations(fields) if list(p) != fields]
    return tag, delim, rng.choice(orders)


def _record(tag, delim, order, fields, values):
    v = dict(zip(fields, values))
    return delim.join([tag] + [str(v[f]) for f in order])


def make_project(i: int, seed: int = 0) -> Project:
    cls, rec, fields, samples = DOMAINS[i % len(DOMAINS)]
    rng = random.Random(f"secretbench-{seed}-{i}")
    tag, delim, order = _secret(rng, fields)
    f1, f2, f3 = fields
    s0, s1, s2 = (_record(tag, delim, order, fields, v) for v in samples)
    other_tag = "".join(chr((ord(c) - 65 + 7) % 26 + 65) for c in tag)
    v0 = dict(zip(fields, map(str, samples[0])))
    v1 = dict(zip(fields, map(str, samples[1])))
    order_txt = ", ".join(order)

    docs = {
        "encode": f'''    def encode(self, {f1}, {f2}, {f3}):
        """
        Encode one {rec} as a string in this project's record format.
        Format: the tag '{tag}', then the fields {order_txt} (in that order), all joined by '{delim}'.
        Values are converted with str().
        :return: str
        >>> c = {cls}()
        >>> c.encode({", ".join(repr(x) for x in samples[0])})
        {s0!r}
        """''',
        "decode": f'''    def decode(self, s):
        """
        Decode a record string produced by `encode` back into a dict with the keys
        '{f1}', '{f2}' and '{f3}'; all values are strings.
        Raise ValueError if s is not a valid record.
        :return: dict
        >>> c = {cls}()
        >>> c.decode(c.encode({", ".join(repr(x) for x in samples[0])}))
        {v0!r}
        """''',
        "is_record": f'''    def is_record(self, s):
        """
        Check whether s is a valid record string as produced by `encode`:
        it must carry this project's tag and exactly three fields.
        :return: bool
        >>> c = {cls}()
        >>> c.is_record('')
        False
        """''',
        "get_field": f'''    def get_field(self, s, name):
        """
        Return the value (a string) of the field `name` ('{f1}', '{f2}' or '{f3}') of the record string s.
        Raise KeyError if name is not one of these fields.
        :return: str
        >>> c = {cls}()
        >>> c.get_field(c.encode({", ".join(repr(x) for x in samples[0])}), '{f2}')
        {v0[f2]!r}
        """''',
    }
    pos = {f: order.index(f) + 1 for f in fields}
    sols = {
        "encode": f'''    def encode(self, {f1}, {f2}, {f3}):
        v = {{'{f1}': {f1}, '{f2}': {f2}, '{f3}': {f3}}}
        return {delim!r}.join([{tag!r}] + [str(v[f]) for f in {order!r}])
''',
        "decode": f'''    def decode(self, s):
        parts = s.split({delim!r}) if isinstance(s, str) else []
        if len(parts) != 4 or parts[0] != {tag!r}:
            raise ValueError("not a record")
        return {{f: parts[i + 1] for i, f in enumerate({order!r})}}
''',
        "is_record": f'''    def is_record(self, s):
        parts = s.split({delim!r}) if isinstance(s, str) else []
        return len(parts) == 4 and parts[0] == {tag!r}
''',
        "get_field": f'''    def get_field(self, s, name):
        pos = {pos!r}
        if name not in pos:
            raise KeyError(name)
        return s.split({delim!r})[pos[name]]
''',
    }
    T = f"{cls}Test"
    tests = {
        "encode": f'''class {T}Encode(unittest.TestCase):
    def test_encode_1(self):
        self.assertEqual({cls}().encode({", ".join(repr(x) for x in samples[0])}), {s0!r})

    def test_encode_2(self):
        self.assertEqual({cls}().encode({", ".join(repr(x) for x in samples[1])}), {s1!r})

    def test_encode_3(self):
        self.assertEqual({cls}().encode({", ".join(repr(x) for x in samples[2])}), {s2!r})
''',
        # visible test (the first) is format-independent
        "decode": f'''class {T}Decode(unittest.TestCase):
    def test_decode_1(self):
        with self.assertRaises(ValueError):
            {cls}().decode('')

    def test_decode_2(self):
        self.assertEqual({cls}().decode({s0!r}), {v0!r})

    def test_decode_3(self):
        self.assertEqual({cls}().decode({s1!r}), {v1!r})

    def test_decode_4(self):
        with self.assertRaises(ValueError):
            {cls}().decode({s0.replace(tag, other_tag, 1)!r})
''',
        "is_record": f'''class {T}IsRecord(unittest.TestCase):
    def test_is_record_1(self):
        self.assertFalse({cls}().is_record(''))

    def test_is_record_2(self):
        self.assertTrue({cls}().is_record({s1!r}))

    def test_is_record_3(self):
        self.assertFalse({cls}().is_record({s1.replace(tag, other_tag, 1)!r}))

    def test_is_record_4(self):
        self.assertFalse({cls}().is_record({delim.join(s2.split(delim)[:3])!r}))

    def test_is_record_5(self):
        self.assertTrue({cls}().is_record({s2!r}))
''',
        "get_field": f'''class {T}GetField(unittest.TestCase):
    def test_get_field_1(self):
        with self.assertRaises(KeyError):
            {cls}().get_field('', 'no_such_field')

    def test_get_field_2(self):
        self.assertEqual({cls}().get_field({s0!r}, '{f1}'), {v0[f1]!r})

    def test_get_field_3(self):
        self.assertEqual({cls}().get_field({s1!r}, '{f3}'), {v1[f3]!r})

    def test_get_field_4(self):
        self.assertEqual({cls}().get_field({s1!r}, '{f2}'), {v1[f2]!r})
''',
    }
    skeleton = (f'class {cls}:\n    """\n    Stores {rec}s as strings in a project-specific record format.\n    """\n\n'
                f'    def __init__(self):\n        pass\n\n' + "\n\n".join(docs[n] for n in docs) + "\n")
    deps = {"encode": [], "decode": ["encode"], "is_record": ["encode"], "get_field": ["encode"]}
    subtasks = [Subtask(name=n, doc=docs[n].strip(), deps=deps[n], visible_test=_first_test_only(tests[n]),
                        hidden_test=tests[n], solution=sols[n]) for n in docs]
    return Project(pid=f"Secret_{seed}_{i}", class_name=cls, skeleton=skeleton, subtasks=subtasks,
                   meta={"benchmark": "secretbench", "secret": {"tag": tag, "delim": delim, "order": order}})


def secret_projects(n: int, seed: int = 0) -> list[Project]:
    return [make_project(i, seed) for i in range(n)]
