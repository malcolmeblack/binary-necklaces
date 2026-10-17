#!/usr/bin/env python3
"""Reproducible v2 acceptance tests using only Python's standard library.

The production calculator is exercised for all n=1..1024 with a 512 MiB heap.
Explicit binary-word enumeration is confined to the independent n<=16 oracle
in THIS TEST. Neither the calculator nor its output verifier enumerates words.
Run: python3 test/validate.py
"""
import copy
import csv
import importlib.util
import json
import math
import sys
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWER_HEADER = ["n", "bitstrings", "bitloops", "factors", "chains", "graphs"]
GRAPH_HEADER = ["n", "name", "chains", "bitloops-per-chain", "bitstrings",
                "bitloops", "factors", "cycle-order", "tree-depth", "signature"]


def command(args, *, cwd=ROOT, ok=True, timeout=600):
    result = subprocess.run(list(map(str, args)), cwd=cwd, text=True,
                            capture_output=True, timeout=timeout)
    if ok and result.returncode:
        raise AssertionError(f"Command failed ({result.returncode}): {args}\n"
                             f"{result.stdout}\n{result.stderr}")
    if not ok and result.returncode == 0:
        raise AssertionError(f"Invalid invocation succeeded: {args}\n{result.stdout}")
    return result


def table(path, header):
    raw = path.read_bytes()
    assert b"\r\n" in raw, f"Missing CSV CRLF terminators: {path}"
    assert b"\n" not in raw.replace(b"\r\n", b""), f"Mixed CSV line endings: {path}"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == header, (path, reader.fieldnames)
        rows = list(reader)
        assert all(None not in row and None not in row.values() for row in rows)
    return rows


def oracle(n):
    """Construct actual necklace graph using binary STRINGS, no GF(2) code."""
    def canonical(word):
        return min(word[i:] + word[:i] for i in range(n))

    necklaces = Counter(canonical(format(w, f"0{n}b")) for w in range(1 << n))
    successor = {
        word: canonical("".join("1" if word[i] != word[(i + 1) % n] else "0"
                                for i in range(n)))
        for word in necklaces
    }
    incoming = {word: [] for word in necklaces}
    for word, linked in successor.items():
        incoming[linked].append(word)
    indegree = {word: len(parents) for word, parents in incoming.items()}
    leaves = deque(word for word, degree in indegree.items() if degree == 0)
    while leaves:
        linked = successor[leaves.popleft()]
        indegree[linked] -= 1
        if indegree[linked] == 0:
            leaves.append(linked)
    cyclic = {word for word, degree in indegree.items() if degree}
    seen, graphs = set(), {}
    components = 0
    for start in sorted(necklaces):
        if start in seen:
            continue
        component, pending = {start}, [start]
        for word in pending:
            for neighbor in [successor[word], *incoming[word]]:
                if neighbor not in component:
                    component.add(neighbor)
                    pending.append(neighbor)
        seen.update(component)
        components += 1
        cycle = component & cyclic
        # Determine depth directly from edges and inspect ALL nodes' indegrees.
        depths = {word: 0 for word in cycle}
        queue = deque(cycle)
        while queue:
            word = queue.popleft()
            for parent in incoming[word]:
                if parent not in depths:
                    depths[parent] = depths[word] + 1
                    queue.append(parent)
        assert set(depths) == component
        levels = defaultdict(set)
        for word, depth in depths.items():
            levels[depth].add(len(incoming[word]))
        assert all(len(degrees) == 1 for degrees in levels.values()), (n, levels)
        signature = "".join(str(next(iter(levels[depth])))
                            for depth in range(max(levels) + 1))
        name = f"G{len(cycle)}-{signature}"
        graph = graphs.setdefault(name, {
            "n": n, "name": name, "chains": 0, "bitloops-per-chain": len(component),
            "bitstrings": 0, "bitloops": 0, "factors": 0,
            "cycle-order": len(cycle), "tree-depth": max(levels), "signature": signature,
        })
        assert graph["bitloops-per-chain"] == len(component), (n, name)
        graph["chains"] += 1
        graph["bitstrings"] += sum(necklaces[word] for word in component)
        graph["bitloops"] += len(component)
        graph["factors"] += sum(necklaces[word] == n for word in component)
    summary = {"n": n, "bitstrings": 1 << n, "bitloops": len(necklaces),
               "factors": sum(period == n for period in necklaces.values()),
               "chains": components, "graphs": len(graphs)}
    assert len(seen) == len(necklaces)
    return summary, sorted(graphs.values(), key=lambda row: (row["cycle-order"], row["signature"]))


def numeric(row):
    return {key: value if key in ("name", "signature") else int(value)
            for key, value in row.items()}


def output_snapshot(output):
    return {str(path.relative_to(output)): path.read_bytes()
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.suffix in (".csv", ".json")}


def validate_logs(folder, n, runs=1):
    records = [json.loads(line) for line in (folder / "log" / f"{n}.log").read_text().splitlines()]
    ids = list(dict.fromkeys(record["run_id"] for record in records))
    assert len(ids) == runs, (n, ids)
    assert all(record["version"] == "2" for record in records), n
    for run_id in ids:
        group = [record for record in records if record["run_id"] == run_id]
        assert group[0]["event"] == "run_start", group[0]
        assert group[-1]["event"] == "run_end", group[-1]
        assert group[-1]["status"] == "SUCCESS", group[-1]


def must_reject(fn, label):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"Verifier accepted {label}")


def verify_small_intersections(verifier):
    """Derive intersections by searching integer relations, without the CRT formula."""
    lattices = [(d, t, s) for d in range(1, 6) for t in range(1, 5)
                for s in range(d)]
    for left in lattices:
        for right in lattices:
            d1, t1, s1 = left
            d2, t2, s2 = right
            d = math.lcm(d1, d2)
            expected = None
            for t in range(1, math.lcm(d1 * t1, d2 * t2) + 1):
                if t % t1 or t % t2:
                    continue
                shifts = [s for s in range(d)
                          if (s - s1 * (t // t1)) % d1 == 0
                          and (s - s2 * (t // t2)) % d2 == 0]
                if shifts:
                    assert len(shifts) == 1
                    expected = (d, t, shifts[0])
                    break
            assert expected is not None
            assert verifier._intersection(left, right) == expected, (left, right, expected)
    assert verifier._intersection((7, 1, 3), (7, 1, 5)) == (7, 7, 0)
    print(f"PASS: {len(lattices) ** 2:,} small relation-lattice intersections against direct integer-relation search, plus the shift-sensitive n=7 case", flush=True)


def verify_tampering(verifier, output, work):
    original = json.loads((output / "certificates/14.json").read_text())
    cases = []
    def changed(label, edit):
        altered = copy.deepcopy(original)
        edit(altered)
        cases.append((label, altered))
    changed("incorrect total", lambda c: c["totals"].__setitem__("chains", c["totals"]["chains"] + 1))
    changed("incorrect rotation order", lambda c: c["states"][-1].__setitem__("rotation_order", 1))
    changed("incorrect quotient order", lambda c: c["states"][-1].__setitem__("cycle_order", c["states"][-1]["cycle_order"] * 2))
    changed("incorrect DP weight", lambda c: c["states"][-1].__setitem__("units", c["states"][-1]["units"] + 1))
    changed("incorrect state shift", lambda c: c["states"][-1].__setitem__("rotation_shift", (c["states"][-1]["rotation_shift"] + 1) % c["states"][-1]["rotation_order"]))
    changed("incorrect local link order", lambda c: c["irreducible_factors"][0]["powers"][-1].__setitem__("link_order", c["irreducible_factors"][0]["powers"][-1]["link_order"] * 2))
    changed("incorrect local rotation shift", lambda c: c["irreducible_factors"][0]["powers"][-1].__setitem__("rotation_shift", (c["irreducible_factors"][0]["powers"][-1]["rotation_shift"] + 1) % c["irreducible_factors"][0]["powers"][-1]["rotation_order"]))
    changed("incorrect local unit count", lambda c: c["irreducible_factors"][0]["powers"][-1].__setitem__("units", c["irreducible_factors"][0]["powers"][-1]["units"] + 1))
    changed("missing state", lambda c: c["states"].pop())
    changed("duplicate state", lambda c: c["states"].append(copy.deepcopy(c["states"][0])))
    changed("missing local power", lambda c: c["irreducible_factors"][0]["powers"].pop())
    changed("wrong annihilator grid count", lambda c: c.__setitem__("annihilator_strata", c["annihilator_strata"] + 1))
    changed("unknown top-level field", lambda c: c.__setitem__("sample", "00000000000000"))
    changed("unknown state field", lambda c: c["states"][0].__setitem__("extra", 0))
    changed("floating-point count", lambda c: c["states"][0].__setitem__("chains", 1.0))
    changed("boolean count", lambda c: c["states"][0].__setitem__("chains", True))
    changed("negative count", lambda c: c["states"][0].__setitem__("chains", -1))
    changed("wrong signature", lambda c: c["states"][0].__setitem__("signature", "220"))
    changed("invalid factor", lambda c: c["irreducible_factors"][0].__setitem__("polynomial", "0x5"))
    changed("incorrect factor multiplicity", lambda c: c["irreducible_factors"][0].__setitem__("multiplicity", 1))
    changed("unknown schema version", lambda c: c.__setitem__("schema_version", "1.6"))
    changed("non-string schema version", lambda c: c.__setitem__("schema_version", ["2"]))
    for n, version in ((65, "2.1"), (129, "2.2"), (257, "2.3"), (513, "2.4")):
        oversized = json.loads((output / "certificates" / f"{n}.json").read_text())
        oversized["schema_version"] = version
        cases.append((f"schema {version} outside its declared range", oversized))
    for label, certificate in cases:
        must_reject(lambda: verifier.verify_certificate(certificate), label)
    duplicate = work / "duplicate-key.json"
    # Whitespace is deliberately independent of the producer's JSON formatting.
    duplicate.write_text('{"n":14,' + json.dumps(original)[1:])
    must_reject(lambda: verifier.load_certificate(duplicate), "duplicate JSON key")
    bad = work / "tampered-output"
    shutil.copytree(output, bad)
    aggregate = bad / "powersets.csv"
    aggregate.write_bytes(aggregate.read_bytes().replace(b"1,2,2,2,1,1", b"1,3,2,2,1,1", 1))
    assert aggregate.read_bytes() != (output / "powersets.csv").read_bytes()
    must_reject(lambda: verifier.verify_directory(bad), "tampered aggregate")
    print(f"PASS: verifier rejected {len(cases) + 2} independent corruptions", flush=True)


def verify_prime_data(verifier, work, build):
    """Alter proof inputs and check both independent validators fail closed."""
    original = verifier.load_certificate(ROOT / "order-factors.json")
    factors = verifier.verify_factor_data(original)
    assert factors and max(factors) > 512
    order_primes = {p for items in original["mersenne_factors"].values() for p in items}
    wide = next(p for p in original["prime_certificates"]
                if p in order_primes and int(p) >= 1 << 64
                and any(int(q) % 2 for q, _ in original["prime_certificates"][p]["factors"]))
    degree = next(d for d, items in original["mersenne_factors"].items() if wide in items)
    partial = next(p for p, proof in original["prime_certificates"].items()
                   if math.prod(int(q) ** exponent for q, exponent in proof["factors"]) < int(p) - 1)
    cases = []
    def changed(label, edit):
        altered = copy.deepcopy(original)
        edit(altered)
        cases.append((label, altered))
    changed("missing wide-prime proof", lambda c: c["prime_certificates"].pop(wide))
    changed("invalid unit witness", lambda c: c["prime_certificates"][wide].__setitem__("witness", "1"))
    changed("modular witness failure", lambda c: c["prime_certificates"][wide].__setitem__("witness", str(int(wide) - 1)))
    changed("incorrect p-1 factor exponent", lambda c: c["prime_certificates"][wide]["factors"][0].__setitem__(1, c["prime_certificates"][wide]["factors"][0][1] + 1))
    changed("insufficient Pocklington bound", lambda c: c["prime_certificates"][wide].__setitem__("factors", [["2", 1]]))
    changed("corrupted partial Pocklington proof", lambda c: c["prime_certificates"][partial].__setitem__("factors", [["2", 1]]))
    changed("cyclic prime dependency", lambda c: c["prime_certificates"][wide].__setitem__("factors", [[wide, 1]]))
    changed("incorrect Mersenne factor product", lambda c: c["mersenne_factors"][degree].append("2"))
    changed("missing required degree", lambda c: c["mersenne_factors"].pop(degree))
    changed("missing newly required degree", lambda c: c["mersenne_factors"].pop(str(max(factors))))
    changed("noncanonical decimal prime", lambda c: c["mersenne_factors"][degree].__setitem__(0, "0" + c["mersenne_factors"][degree][0]))
    changed("1025-bit prime text", lambda c: c["mersenne_factors"][degree].__setitem__(0, str(1 << 1024)))
    changed("overlong 310-digit prime text", lambda c: c["mersenne_factors"][degree].__setitem__(0, "1" + "0" * 309))
    changed("excessive proof exponent", lambda c: c["prime_certificates"][wide]["factors"][0].__setitem__(1, 1024))
    changed("unknown proof field", lambda c: c["prime_certificates"][wide].__setitem__("unchecked", True))
    changed("floating-point exponent", lambda c: c["prime_certificates"][wide]["factors"][0].__setitem__(1, 1.0))
    for label, data in cases:
        must_reject(lambda: verifier.verify_factor_data(data), label)
    harness = work / "ProofDataCheck.java"
    harness.write_text("""import java.nio.file.Files;
import java.nio.file.Path;
final class ProofDataCheck {
    public static void main(String[] args) throws Exception {
        if (!Files.readString(Path.of(args[0])).equals(OrderFactorData.JSON))
            throw new AssertionError("Java and Python factor data differ");
        for (int i = 0; i < args.length; ++i) {
            boolean accepted = false;
            try {
                ExactInteger.verifyFactorData(Json.parse(Files.readString(Path.of(args[i]))));
                accepted = true;
            } catch (RuntimeException rejected) {
                if (i == 0) throw rejected;
            }
            if (accepted != (i == 0)) throw new AssertionError("Unexpected proof validation: " + args[i]);
        }
    }
}
""")
    command(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "--release", "17",
             "-cp", build, "-d", build, harness])
    paths = [ROOT / "order-factors.json"]
    for index, (label, data) in enumerate(cases):
        path = work / f"bad-factor-proof-{index}.json"
        path.write_text(json.dumps(data))
        paths.append(path)
    command(["java", "-Xmx512m", "-cp", build, "ProofDataCheck", *paths])
    print(f"PASS: identical Java/Python exact factor data; both validators reject {len(cases)} prime-proof/factor-data corruptions", flush=True)


def run_tests():
    started = time.monotonic()
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("verify_output", ROOT / "verify_output.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    with zipfile.ZipFile(ROOT / "test/fixtures.zip") as archive, tempfile.TemporaryDirectory(prefix="java-ai-test-") as temporary:
        fixtures = zipfile.Path(archive)
        work = Path(temporary)
        build = work / "build"
        build.mkdir()
        command(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "--release", "17",
                 "-Xlint:all", "-d", build, *sorted(ROOT.glob("*.java"))])
        verify_prime_data(verifier, work, build)
        (build / "ProofDataCheck.class").unlink()
        jar = work / "java-ai.jar"
        command(["java", "-m", "jdk.jartool/sun.tools.jar.Main", "--create", "--file", jar,
                 "--main-class", "Main", "-C", build, "."])
        def args(folder, threads=32, *extra):
            return ["java", "-Xmx512m", "-jar", jar, *map(str, extra), "--threads", str(threads),
                    "--output", str(folder / "output"), "--log", str(folder / "log"),
                    "--progress-seconds", "0.1"]
        baseline, parallel = work / "serial", work / "parallel"
        # No positional n and no range options must default to all n=1..1024.
        command(args(baseline, 1), timeout=600)
        # Test the user's exact no-argument invocation and default directories.
        parallel.mkdir()
        command(["java", "-Xmx512m", "-jar", jar], cwd=parallel, timeout=600)
        output = baseline / "output"
        assert {int(p.stem) for p in (output / "certificates").glob("*.json")} == set(range(1, 1025))
        assert output_snapshot(output) == output_snapshot(parallel / "output")
        assert not list(output.glob("chains-*.csv"))
        totals = {int(row["n"]): numeric(row) for row in table(output / "powersets.csv", POWER_HEADER)}
        graphs = defaultdict(list)
        for row in table(output / "graphs.csv", GRAPH_HEADER):
            graphs[int(row["n"])].append(numeric(row))
        assert list(totals) == list(range(1, 1025))
        assert list(graphs) == list(range(1, 1025))
        for n in range(1, 1025):
            assert totals[n]["bitstrings"] == 1 << n
            validate_logs(baseline, n)
            validate_logs(parallel, n)
        assert totals[64]["chains"] == 1 and totals[64]["bitstrings"] == 18446744073709551616
        assert totals[128]["chains"] == 1 and totals[128]["bitstrings"] == 340282366920938463463374607431768211456
        assert totals[256]["chains"] == 1 and totals[256]["bitstrings"] == 1 << 256
        assert totals[512]["chains"] == 1 and totals[512]["bitstrings"] == 1 << 512
        assert totals[1024]["chains"] == 1 and totals[1024]["bitstrings"] == 1 << 1024
        assert graphs[1024][0]["tree-depth"] == 1024
        assert len(graphs[1024][0]["signature"]) == 1025
        verifier.verify_directory(output)
        print("PASS: default n=1..1024, 512 MiB heap, 1/32 threads byte-identical CSV/certificates; all certificates independently verified", flush=True)

        for version, limit in (("21", 64), ("22", 128), ("23", 256), ("24", 512)):
            for suffix, header, observations in (
                    ("powersets.csv", POWER_HEADER, totals),
                    ("graphs.csv", GRAPH_HEADER, graphs)):
                name = f"v{version}-{suffix}"
                expected = defaultdict(list)
                for row in table(fixtures / name, header):
                    expected[int(row["n"])].append(numeric(row))
                assert list(expected) == list(range(1, limit + 1))
                for n, rows in expected.items():
                    assert rows == ([observations[n]] if suffix == "powersets.csv" else observations[n]), (name, n)
            print(f"PASS: every powerset and graph row for n=1..{limit} equals the user's frozen version {version[0]}.{version[1]} output", flush=True)

        seven = json.loads((output / "certificates/7.json").read_text())
        local_seven = {f["polynomial"]: f["powers"][0] for f in seven["irreducible_factors"]}
        assert {poly: (p["rotation_order"], p["cycle_order"], p["rotation_shift"])
                for poly, p in local_seven.items()} == {"0xb": (7, 1, 3), "0xd": (7, 1, 5)}
        assert any((s["rotation_order"], s["cycle_order"], s["rotation_shift"]) == (7, 7, 0)
                   for s in seven["states"])
        for n in (65, 67, 83, 107, 121, 126, 127, 128, 131, 139, 149, 163, 179, 211, 227,
                  251, 252, 254, 255, 256, 257, 263, 283, 359, 383, 419, 443, 467,
                  479, 487, 491, 503, 504, 508, 510, 511, 512, 513, 521, 631, 701,
                  757, 811, 863, 911, 947, 971, 1008, 1016, 1018, 1019, 1020, 1021, 1022, 1023, 1024):
            certificate = json.loads((output / "certificates" / f"{n}.json").read_text())
            assert certificate["schema_version"] == "2" and certificate["n"] == n
            assert certificate["totals"]["bitstrings"] == 1 << n
            assert sum(state["units"] for state in certificate["states"]) == 1 << (n - certificate["q"])
            if n not in (128, 256, 512, 1024):
                assert int(certificate["core_polynomial"], 16).bit_length() > 64
        for n in (126, 127, 252, 254, 255):
            certificate = json.loads((output / "certificates" / f"{n}.json").read_text())
            assert len(certificate["states"]) < certificate["annihilator_strata"]
        verify_small_intersections(verifier)
        for n, annihilators, bound in ((252, 244140625, 3450), (254, 387420489, 650), (255, 17179869184, 960)):
            certificate = json.loads((output / "certificates" / f"{n}.json").read_text())
            assert certificate["annihilator_strata"] == annihilators
            assert len(certificate["states"]) <= bound
        # Independent factor counts follow from sum(phi(d)/ord_d(2)) for d|m, d>1.
        for n, annihilators in ((504, 282429536481), (508, 3814697265625),
                                (510, 16677181699666569), (511, 288230376151711744),
                                (1008, 582622237229761), (1016, 150094635296999121),
                                (1020, 582076609134674072265625),
                                (1022, 4710128697246244834921603689),
                                (1023, 81129638414606681695789005144064)):
            certificate = json.loads((output / "certificates" / f"{n}.json").read_text())
            assert certificate["annihilator_strata"] == annihilators
            assert len(certificate["states"]) < annihilators
        print("PASS: wide-polynomial and prime-order boundaries, compressed n=252/254/255/504/508/510/511/1008/1016/1020/1022/1023, and exact 2^1024 word accounting", flush=True)

        for n in range(1, 17):
            expected_total, expected_graphs = oracle(n)
            assert totals[n] == expected_total, (n, totals[n], expected_total)
            assert graphs[n] == expected_graphs, (n, graphs[n], expected_graphs)
        print("PASS: n=1..16 exhaustive string/necklace/functional-graph oracle: 131,070 words; every graph shape and weighted count", flush=True)

        fixture = json.loads((fixtures / "v1-observed-counts.json").read_text())
        for run in fixture["completed_runs"]:
            n = run["n"]
            expected = {key: run[key] for key in ("n", "bitstrings", "bitloops", "factors", "graphs")}
            expected["chains"] = run["actual_chains"]
            assert totals[n] == expected, n
            assert {g["name"]: g["chains"] for g in graphs[n]} == run["graph_counts"], n
        assert totals[50]["chains"] == fixture["n50_forecast"]["actual_chains"]
        print("PASS: all completed v1 n=1..49 log totals and actual graph counts; separately labelled n=50 arithmetic forecast", flush=True)

        plan = work / "plan"
        command(args(plan, 32, "--plan"))
        assert not plan.exists(), "--plan created output/log directories"
        for extra in ((0,), (1025,), ("bad",), (14, 15), ("--from", 10, "--to", 9),
                      ("--from", 0, "--to", 3), ("--from", 1022, "--to", 1025),
                      (14, "--from", 1), ("--threads", 0), ("--threads", 257),
                      ("--progress-seconds", 0), (14, "--rebuild-aggregates"),
                      ("--from",), ("--unknown",)):
            bad = work / "invalid"
            # Avoid appending a valid --threads option after an invalid one.
            invocation = ["java", "-Xmx512m", "-jar", jar, *map(str, extra),
                          "--output", str(bad / "output"), "--log", str(bad / "log")]
            command(invocation, ok=False)
            assert not bad.exists(), (extra, "invalid CLI produced files")
        print("PASS: --plan writes nothing; invalid n/ranges/options fail before output/log creation", flush=True)

        before = output_snapshot(output)
        command(args(baseline, 32, 14))
        assert output_snapshot(output) == before
        validate_logs(baseline, 14, runs=2)
        command(args(baseline, 1, "--from", 13, "--to", 15))
        assert output_snapshot(output) == before
        validate_logs(baseline, 14, runs=3)
        print("PASS: single/range reruns preserve other n, deterministically replace entries, and append distinguishable log runs", flush=True)

        concurrent = work / "concurrent"
        invocations = [args(concurrent, 4, n) for n in (13, 14, 15, 16)]
        jobs = [subprocess.Popen(list(map(str, invocation)), cwd=ROOT, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for invocation in invocations]
        for job in jobs:
            stdout, stderr = job.communicate(timeout=120)
            assert job.returncode == 0, (job.returncode, stdout, stderr)
        observed = verifier.verify_directory(concurrent / "output")
        assert [row["n"] for row in observed] == [13, 14, 15, 16]
        print("PASS: four concurrent publishers preserve every certificate and aggregate entry", flush=True)

        mixed = work / "mixed"
        (mixed / "output/certificates").mkdir(parents=True)
        old_paths, preserved = {}, {}
        for version, n in (("21", 14), ("22", 65), ("23", 129), ("24", 257)):
            fixture_path = fixtures / f"v{version}-certificate-{n}.json"
            preserved[n] = fixture_path.read_bytes()
            old_paths[n] = mixed / "output/certificates" / f"{n}.json"
            old_paths[n].write_bytes(preserved[n])
        command(args(mixed, 1, "--rebuild-aggregates"))
        assert all(old_paths[n].read_bytes() == preserved[n] for n in preserved)
        rows = verifier.verify_directory(mixed / "output")
        assert rows == [totals[14], totals[65], totals[129], totals[257]]
        command(args(mixed, 4, 513))
        assert all(old_paths[n].read_bytes() == preserved[n] for n in preserved)
        rows = verifier.verify_directory(mixed / "output")
        assert rows == [totals[14], totals[65], totals[129], totals[257], totals[513]]
        for n in (14, 65, 129, 257):
            command(args(mixed, 1, n))
            assert old_paths[n].read_bytes() == (output / "certificates" / f"{n}.json").read_bytes()
            assert json.loads(old_paths[n].read_text())["schema_version"] == "2"
            assert verifier.verify_directory(mixed / "output") == rows
        print("PASS: mixed 2.1/2.2/2.3/2.4/2 certificate import, aggregate rebuild, and selective deterministic migration", flush=True)

        old = work / "legacy"
        (old / "output").mkdir(parents=True)
        (old / "output/powersets.csv").write_text("n,bitstrings,bitloops,factors,sym-chains,asym-chains,graphs\n1,2,2,2,1,0,1\n")
        (old / "output/chains-1.csv").write_bytes(b"keep original representatives\n")
        snapshot = output_snapshot(old / "output")
        command(args(old, 1, 1), ok=False)
        assert output_snapshot(old / "output") == snapshot
        untouched = work / "unrelated-chains"
        (untouched / "output").mkdir(parents=True)
        sentinel = untouched / "output/chains-14.csv"
        sentinel.write_bytes(b"keep original representatives\n")
        command(args(untouched, 1, 14))
        assert sentinel.read_bytes() == b"keep original representatives\n"
        print("PASS: legacy aggregate headers refused without output changes; existing chain files left untouched", flush=True)

        recovery = work / "recovery"
        shutil.copytree(output, recovery / "output")
        (recovery / "output/powersets.csv").unlink()
        (recovery / "output/graphs.csv").write_bytes((recovery / "output/graphs.csv").read_bytes().split(b"\r\n", 1)[0] + b"\r\n")
        command(args(recovery, 1, "--rebuild-aggregates"))
        assert output_snapshot(recovery / "output") == before
        print("PASS: aggregate repair reconstructs exact CSV bytes from certificates after missing/stale aggregates", flush=True)
        verify_tampering(verifier, output, work)
    print(f"PASS: complete v2 acceptance suite ({time.monotonic() - started:.2f} seconds)", flush=True)


if __name__ == "__main__":
    run_tests()
