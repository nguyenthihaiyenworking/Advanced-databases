
"""CampusGraph: a course-prerequisite and friendship graph in Neo4j.

Usage:
    python campus.py setup     # (re)load the dataset, wipes the database first
    python campus.py check     # run every task and compare with expected output
"""

import os
import sys

from neo4j import GraphDatabase


# ---------------------------------------------------------------- connection

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (
    os.getenv("NEO4J_USER", "neo4j"),
    os.getenv("NEO4J_PASSWORD", "learnneo4j")
)

driver = GraphDatabase.driver(URI, auth=AUTH)


# ---------------------------------------------------------------- dataset

COURSES = [
    ("CS101", "Intro to Programming", 3),
    ("MATH101", "Calculus", 3),
    ("MATH102", "Linear Algebra", 3),
    ("STAT101", "Probability and Statistics", 3),
    ("CS102", "Data Structures", 3),
    ("DB201", "Databases", 3),
    ("VIZ201", "Data Visualization", 2),
    ("ML201", "Machine Learning", 4),
    ("DE301", "Data Engineering", 3),
    ("DB301", "NoSQL Databases", 3),
    ("DL301", "Deep Learning", 4),
    ("NLP401", "Natural Language Processing", 3),
    ("CAP401", "Capstone Project", 6),
]

REQUIRES = [
    ("MATH102", "MATH101"),
    ("STAT101", "MATH101"),
    ("CS102", "CS101"),
    ("DB201", "CS102"),
    ("VIZ201", "CS101"),
    ("VIZ201", "STAT101"),
    ("ML201", "CS102"),
    ("ML201", "MATH102"),
    ("ML201", "STAT101"),
    ("DE301", "DB201"),
    ("DE301", "CS102"),
    ("DB301", "DB201"),
    ("DL301", "ML201"),
    ("NLP401", "DL301"),
    ("CAP401", "DB301"),
    ("CAP401", "ML201"),
]

STUDENTS = [
    ("S01", "An", 3),
    ("S02", "Binh", 2),
    ("S03", "Chi", 3),
    ("S04", "Dung", 1),
    ("S05", "Giang", 2),
    ("S06", "Hoa", 3),
    ("S07", "Khoa", 2),
    ("S08", "Lan", 1),
    ("S09", "Minh", 3),
    ("S10", "Phuong", 2),
]

PASSED = {
    "S01": {
        "CS101": 8.5, "MATH101": 7.0, "CS102": 8.0,
        "MATH102": 6.5, "STAT101": 7.5, "DB201": 9.0
    },
    "S02": {
        "CS101": 7.0, "MATH101": 8.0,
        "STAT101": 8.5, "VIZ201": 9.0
    },
    "S03": {
        "CS101": 9.0, "MATH101": 9.5, "MATH102": 9.0,
        "STAT101": 8.0, "CS102": 8.5, "ML201": 9.0,
        "DB201": 7.5
    },
    "S04": {
        "CS101": 6.5, "MATH101": 7.5
    },
    "S05": {
        "CS101": 8.0, "CS102": 7.5,
        "DB201": 8.0, "MATH101": 6.0
    },
    "S06": {
        "CS101": 9.5, "MATH101": 8.5, "MATH102": 8.0,
        "STAT101": 9.0, "CS102": 9.0, "DB201": 8.5,
        "DB301": 9.0, "ML201": 8.0
    },
    "S07": {
        "CS101": 7.5, "MATH101": 7.0,
        "STAT101": 6.5, "CS102": 7.0
    },
    "S08": {
        "CS101": 8.0
    },
    "S09": {
        "CS101": 8.0, "MATH101": 8.0, "MATH102": 7.5,
        "STAT101": 7.0, "CS102": 8.0, "DB201": 8.0,
        "ML201": 7.5, "DL301": 8.5, "VIZ201": 8.0
    },
    "S10": {
        "CS101": 9.0, "MATH101": 9.0,
        "STAT101": 8.0, "VIZ201": 8.5, "CS102": 7.5
    },
}

FRIENDS = [
    ("S01", "S02"),
    ("S01", "S05"),
    ("S02", "S04"),
    ("S04", "S08"),
    ("S05", "S07"),
    ("S07", "S10"),
    ("S03", "S06"),
    ("S03", "S09"),
    ("S06", "S09"),
    ("S09", "S10"),
    ("S08", "S10"),
]


# ---------------------------------------------------------------- setup

def setup():
    """Wipe the database, create constraints and load the dataset."""

    q = lambda cypher, **params: driver.execute_query(cypher, params)

    # Clear database
    q("MATCH (n) DETACH DELETE n")

    # Create constraints
    q("""
        CREATE CONSTRAINT student_id IF NOT EXISTS
        FOR (s:Student) REQUIRE s.id IS UNIQUE
    """)

    q("""
        CREATE CONSTRAINT course_code IF NOT EXISTS
        FOR (c:Course) REQUIRE c.code IS UNIQUE
    """)

    # Create courses
    q("""
        UNWIND $rows AS r
        MERGE (c:Course {code: r[0]})
        SET c.title = r[1], c.credits = r[2]
    """, rows=[list(c) for c in COURSES])

    # Create prerequisite relationships
    q("""
        UNWIND $rows AS r
        MATCH (c:Course {code: r[0]}),
              (p:Course {code: r[1]})
        MERGE (c)-[:REQUIRES]->(p)
    """, rows=[list(r) for r in REQUIRES])

    # Create students
    q("""
        UNWIND $rows AS r
        MERGE (s:Student {id: r[0]})
        SET s.name = r[1], s.year = r[2]
    """, rows=[list(s) for s in STUDENTS])

    # Create PASSED relationships
    q("""
        UNWIND $rows AS r
        MATCH (s:Student {id: r.sid}),
              (c:Course {code: r.code})
        MERGE (s)-[p:PASSED]->(c)
        SET p.grade = r.grade
    """, rows=[
        {"sid": s, "code": c, "grade": g}
        for s, courses in PASSED.items()
        for c, g in courses.items()
    ])

    # Create friendship relationships
    q("""
        UNWIND $rows AS r
        MATCH (a:Student {id: r[0]}),
              (b:Student {id: r[1]})
        MERGE (a)-[:FRIEND]->(b)
    """, rows=[list(f) for f in FRIENDS])

    # Print database counts
    counts = driver.execute_query("""
        MATCH (n)
        RETURN labels(n)[0] AS label, count(*) AS n
        ORDER BY label
    """).records

    print("loaded:", {r["label"]: r["n"] for r in counts})


# ---------------------------------------------------------------- Task 1

def passed_courses(student_id):
    """Return passed courses with grades, best grade first."""

    records = driver.execute_query("""
        MATCH (s:Student {id: $sid})-[p:PASSED]->(c:Course)
        RETURN c.code AS code, p.grade AS grade
        ORDER BY grade DESC, code ASC
    """, sid=student_id).records

    return [
        (r["code"], r["grade"])
        for r in records
    ]


# ---------------------------------------------------------------- Task 2

def prerequisite_chain(code):
    """Return all direct and indirect prerequisites with minimum depth."""

    records = driver.execute_query("""
        MATCH path =
            (c:Course {code: $code})-[:REQUIRES*1..]->(p:Course)

        WITH p, min(length(path)) AS depth

        RETURN p.code AS code, depth
        ORDER BY depth ASC, code ASC
    """, code=code).records

    return [
        (r["code"], r["depth"])
        for r in records
    ]


# ---------------------------------------------------------------- Task 3

def eligible_courses(student_id):
    """Return courses not passed whose direct prerequisites are all passed."""

    records = driver.execute_query("""
        MATCH (s:Student {id: $sid}), (c:Course)

        WHERE NOT EXISTS {
            MATCH (s)-[:PASSED]->(c)
        }

        AND NOT EXISTS {
            MATCH (c)-[:REQUIRES]->(p:Course)
            WHERE NOT EXISTS {
                MATCH (s)-[:PASSED]->(p)
            }
        }

        RETURN c.code AS code
        ORDER BY code ASC
    """, sid=student_id).records

    return [
        r["code"]
        for r in records
    ]


# ---------------------------------------------------------------- Task 4

def suggest_friends(student_id, k=3):
    """Recommend students based on shared passed courses."""

    records = driver.execute_query("""
        MATCH (s:Student {id: $sid}),
              (candidate:Student)

        WHERE candidate.id <> s.id

        AND NOT EXISTS {
            MATCH (s)-[:FRIEND]-(candidate)
        }

        OPTIONAL MATCH
            (s)-[:PASSED]->(c:Course)<-[:PASSED]-(candidate)

        WITH candidate, count(DISTINCT c) AS shared

        RETURN candidate.name AS name, shared
        ORDER BY shared DESC, name ASC
        LIMIT $k
    """, sid=student_id, k=k).records

    return [
        (r["name"], r["shared"])
        for r in records
    ]


# ---------------------------------------------------------------- Task 5

def connection(a_id, b_id):
    """Return names along the shortest undirected FRIEND path."""

    records = driver.execute_query("""
        MATCH (a:Student {id: $a_id}),
              (b:Student {id: $b_id})

        MATCH path = shortestPath(
            (a)-[:FRIEND*]-(b)
        )

        RETURN [n IN nodes(path) | n.name] AS names
    """, a_id=a_id, b_id=b_id).records

    if not records:
        return []

    return records[0]["names"]


# ---------------------------------------------------------------- Task 6

def bottleneck_courses(k=3):
    """Return courses with the most direct and indirect dependants."""

    records = driver.execute_query("""
        MATCH (c:Course)

        OPTIONAL MATCH
            (dependent:Course)-[:REQUIRES*1..]->(c)

        WITH c, count(DISTINCT dependent) AS dependents

        RETURN c.code AS code, dependents
        ORDER BY dependents DESC, code ASC
        LIMIT $k
    """, k=k).records

    return [
        (r["code"], r["dependents"])
        for r in records
    ]


# ---------------------------------------------------------------- Task 7

def _record_pass_tx(tx, student_id, code, grade):
    """Record a pass safely inside one transaction."""

    # Step 1: Check whether student and course exist
    record = tx.run("""
        OPTIONAL MATCH (s:Student {id: $sid})
        OPTIONAL MATCH (c:Course {code: $code})

        RETURN
            s IS NOT NULL AS student_exists,
            c IS NOT NULL AS course_exists
    """, sid=student_id, code=code).single()

    if not record["student_exists"] or not record["course_exists"]:
        raise ValueError(
            f"unknown student or course: {student_id}, {code}"
        )

    # Step 2: Find missing direct prerequisites
    missing = tx.run("""
        MATCH (c:Course {code: $code})-[:REQUIRES]->(p:Course)

        WHERE NOT EXISTS {
            MATCH (:Student {id: $sid})-[:PASSED]->(p)
        }

        RETURN p.code AS code
        ORDER BY code ASC
    """, sid=student_id, code=code).value()

    if missing:
        raise ValueError(
            f"missing prerequisites: {missing}"
        )

    # Step 3: Create or update PASSED relationship
    tx.run("""
        MATCH (s:Student {id: $sid}),
              (c:Course {code: $code})

        MERGE (s)-[p:PASSED]->(c)

        SET p.grade = $grade
    """, sid=student_id, code=code, grade=grade).consume()


def record_pass(student_id, code, grade):
    """Record a passed course inside one write transaction."""

    with driver.session() as session:
        session.execute_write(
            _record_pass_tx,
            student_id,
            code,
            grade
        )


# ---------------------------------------------------------------- self-check

def check():
    setup()

    def expect_error(fn):
        try:
            fn()
        except ValueError as e:
            return str(e)

        return None

    def after_record():
        record_pass("S08", "CS102", 7.0)

        # Same pass again: update grade, not duplicate
        record_pass("S08", "CS102", 7.5)

        n = driver.execute_query("""
            MATCH (:Student {id: 'S08'})
                  -[p:PASSED]->
                  (:Course {code: 'CS102'})

            RETURN count(p) AS n, max(p.grade) AS g
        """).records[0]

        return (
            n["n"],
            n["g"],
            eligible_courses("S08")
        )

    tests = [
        (
            "1 passed_courses",
            lambda: passed_courses("S04"),
            [("MATH101", 7.5), ("CS101", 6.5)]
        ),

        (
            "2 prerequisite_chain",
            lambda: prerequisite_chain("DE301"),
            [("CS102", 1), ("DB201", 1), ("CS101", 2)]
        ),

        (
            "3 eligible_courses",
            lambda: eligible_courses("S01"),
            ["DB301", "DE301", "ML201", "VIZ201"]
        ),

        (
            "4 suggest_friends",
            lambda: suggest_friends("S02"),
            [("Minh", 4), ("Phuong", 4), ("Chi", 3)]
        ),

        (
            "5 connection",
            lambda: connection("S01", "S08"),
            ["An", "Binh", "Dung", "Lan"]
        ),

        (
            "6 bottleneck_courses",
            lambda: bottleneck_courses(),
            [("CS101", 9), ("CS102", 7), ("MATH101", 7)]
        ),

        (
            "7a record_pass refuses",
            lambda: expect_error(
                lambda: record_pass("S04", "ML201", 8.0)
            ),
            "missing prerequisites: ['CS102', 'MATH102', 'STAT101']"
        ),

        (
            "7b record_pass writes",
            after_record,
            (1, 7.5, ["DB201", "MATH101"])
        ),
    ]

    for name, fn, expected in tests:
        try:
            got = fn()

        except NotImplementedError:
            print(f"TODO  {name}")
            continue

        except Exception as e:
            print(
                f"ERROR {name}: "
                f"{type(e).__name__}: {e}"
            )
            continue

        status = "PASS " if got == expected else "FAIL "

        print(f"{status} {name}")

        if got != expected:
            print(
                f"        expected {expected}\n"
                f"        got      {got}"
            )


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    try:
        {"setup": setup, "check": check}[cmd]()

    finally:
        driver.close()
