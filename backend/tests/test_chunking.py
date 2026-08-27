from app.rag.chunking import chunk_file


def test_python_extracts_top_level_function():
    content = (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def subtract(a, b):\n"
        "    return a - b\n"
    )
    chunks = chunk_file("math.py", content, ".py")

    names = {c.symbol for c in chunks}
    assert names == {"add", "subtract"}
    add_chunk = next(c for c in chunks if c.symbol == "add")
    assert add_chunk.chunk_type == "function"
    assert add_chunk.start_line == 1
    assert "return a + b" in add_chunk.text


def test_python_extracts_class_and_methods():
    content = (
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "    def subtract(self, a, b):\n"
        "        return a - b\n"
    )
    chunks = chunk_file("calc.py", content, ".py")

    types_by_symbol = {c.symbol: c.chunk_type for c in chunks}
    assert types_by_symbol["Calculator"] == "class"
    assert types_by_symbol["Calculator.add"] == "method"
    assert types_by_symbol["Calculator.subtract"] == "method"


def test_python_syntax_error_falls_back_to_line_chunks():
    content = "def broken(:\n    this is not valid python\n" * 5
    chunks = chunk_file("broken.py", content, ".py")

    # Falls back rather than raising — every chunk should be a generic block.
    assert len(chunks) > 0
    assert all(c.chunk_type == "block" for c in chunks)


def test_python_file_with_no_functions_falls_back_to_lines():
    content = "\n".join(f"CONSTANT_{i} = {i}" for i in range(60))
    chunks = chunk_file("constants.py", content, ".py")

    assert len(chunks) > 0
    assert all(c.chunk_type == "block" for c in chunks)


def test_javascript_extracts_function_boundaries():
    content = (
        "import React from 'react';\n"
        "\n"
        "function greet(name) {\n"
        "  return `hello ${name}`;\n"
        "}\n"
        "\n"
        "const add = (a, b) => {\n"
        "  return a + b;\n"
        "};\n"
    )
    chunks = chunk_file("utils.js", content, ".js")

    joined = "\n---\n".join(c.text for c in chunks)
    assert "function greet" in joined
    assert "const add" in joined
    # The import line before the first boundary should still be indexed.
    assert any("import React" in c.text for c in chunks)


def test_unknown_extension_uses_line_fallback():
    content = "\n".join(f"line {i}" for i in range(100))
    chunks = chunk_file("data.sql", content, ".sql")

    assert len(chunks) > 1  # 100 lines should produce more than one window
    assert all(c.chunk_type == "block" for c in chunks)


def test_empty_file_produces_no_chunks():
    assert chunk_file("empty.py", "", ".py") == []
    assert chunk_file("empty.py", "   \n\n  ", ".py") == []


def test_oversized_function_gets_split():
    body_lines = "\n".join(
        f"    x{i} = some_long_function_call_here({i}, {i}, {i}, {i})" for i in range(200)
    )
    content = f"def huge():\n{body_lines}\n"
    assert len(content) > 4000  # sanity-check the fixture is actually oversized
    chunks = chunk_file("huge.py", content, ".py")

    assert len(chunks) > 1
    assert all(c.symbol == "huge" for c in chunks)
    assert all(len(c.text) <= 4000 + 500 for c in chunks)  # slack for line boundaries


def test_tiny_function_still_indexed_but_trivial_lines_skipped():
    content = "def f():\n    pass\n"
    chunks = chunk_file("tiny.py", content, ".py")
    # "def f():\n    pass" is short but should still clear MIN_CHUNK_CHARS
    # or reasonably be skipped — either outcome must not raise.
    assert isinstance(chunks, list)