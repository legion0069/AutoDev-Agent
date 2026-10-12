"""
tests/test_duplication_detector.py - Unit tests for AutoDev Duplication Detector (v2.7)

Validates:
- Exact duplicate code block detection
- Near duplicate code block detection (token & normalization hashing)
- Repeated condition detection across multiple files
- Repeated string / numeric literal detection
- Repeated SQL query string detection
- Repeated Regex pattern detection
"""

import pytest
from core.duplication_detector import DuplicationDetector
from core.quality_models import DuplicationBlock


def test_exact_duplicates_across_files():
    """Detects identical blocks of code residing in different files."""
    code_block = """
def authenticate_user(username, password):
    if not username or not password:
        raise ValueError("Missing credentials")
    token = hash_credentials(username, password)
    return {"token": token, "status": "active"}
"""
    files = {
        "services/auth.py": code_block,
        "legacy/old_auth.py": "# Old copy\n" + code_block,
    }

    detector = DuplicationDetector(min_lines=4)
    duplicates = detector.detect_duplicates(files)
    assert len(duplicates) >= 1
    dup = duplicates[0]
    assert len(dup.occurrences) >= 2
    paths = {occ.file_path for occ in dup.occurrences}
    assert "services/auth.py" in paths
    assert "legacy/old_auth.py" in paths


def test_near_duplicates_with_variable_renaming():
    """Detects blocks that are structurally identical with renamed identifiers."""
    block1 = """
def calculate_order_total(items, discount_rate):
    subtotal = sum(item.price * item.quantity for item in items)
    discount = subtotal * discount_rate
    tax = (subtotal - discount) * 0.08
    return subtotal - discount + tax
"""
    block2 = """
def compute_invoice_sum(products, rebate_ratio):
    subtotal = sum(product.price * product.quantity for product in products)
    discount = subtotal * rebate_ratio
    tax = (subtotal - discount) * 0.08
    return subtotal - discount + tax
"""
    files = {
        "finance/order.py": block1,
        "finance/invoice.py": block2,
    }

    detector = DuplicationDetector(min_lines=4, similarity_threshold=0.85)
    duplicates = detector.detect_duplicates(files)
    assert len(duplicates) >= 1


def test_repeated_conditions():
    """Identifies identical or repeated complex branch conditions."""
    files = {
        "api/routes.py": """
def get_resource(user, res):
    if user.is_authenticated and user.has_permission("read") and not user.is_suspended:
        return res
    return None
""",
        "api/admin.py": """
def delete_resource(user, res):
    if user.is_authenticated and user.has_permission("read") and not user.is_suspended:
        do_delete(res)
    return None
""",
    }

    detector = DuplicationDetector()
    repeated_conds = detector.detect_repeated_conditions(files)
    assert len(repeated_conds) >= 1
    condition_text = list(repeated_conds.keys())[0]
    assert "user.is_authenticated" in condition_text


def test_repeated_string_literals():
    """Identifies magic strings repeated across the codebase."""
    files = {
        "module_a.py": """
def log_event():
    print("CONNECTION_TIMEOUT_ERROR_CODE_504")
    print("USER_SESSION_EXPIRED")
""",
        "module_b.py": """
def handle_error():
    raise RuntimeError("CONNECTION_TIMEOUT_ERROR_CODE_504")
""",
        "module_c.py": """
def alert():
    notify("CONNECTION_TIMEOUT_ERROR_CODE_504")
""",
    }

    detector = DuplicationDetector(min_literal_occurrences=3)
    repeated_literals = detector.detect_repeated_literals(files)
    assert "CONNECTION_TIMEOUT_ERROR_CODE_504" in repeated_literals
    assert len(repeated_literals["CONNECTION_TIMEOUT_ERROR_CODE_504"]) >= 3


def test_repeated_sql_queries():
    """Identifies raw duplicated SQL queries that should be centralized."""
    sql = "SELECT id, username, email FROM users WHERE is_active = 1 ORDER BY created_at DESC"
    files = {
        "handlers/users.py": f'db.query("{sql}")',
        "services/auth.py": f'cursor.execute("{sql}")',
    }

    detector = DuplicationDetector()
    repeated_sql = detector.detect_repeated_sql(files)
    assert len(repeated_sql) >= 1
    found_sql = list(repeated_sql.keys())[0]
    assert "SELECT" in found_sql and "FROM users" in found_sql


def test_repeated_regex_patterns():
    """Identifies duplicate uncompiled regex patterns across files."""
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    files = {
        "validators/email.py": f're.match(r"{regex}", email_str)',
        "models/user.py": f're.compile(r"{regex}")',
    }

    detector = DuplicationDetector()
    repeated_regex = detector.detect_repeated_regex(files)
    assert len(repeated_regex) >= 1


def test_no_duplication_in_clean_workspace():
    """Clean distinct files should yield 0 duplication blocks."""
    files = {
        "math_utils.py": "def add(a, b):\n    return a + b\n",
        "string_utils.py": "def capitalize_words(s):\n    return s.title()\n",
    }
    detector = DuplicationDetector(min_lines=3)
    duplicates = detector.detect_duplicates(files)
    assert len(duplicates) == 0
