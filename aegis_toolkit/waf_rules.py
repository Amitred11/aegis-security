# aegis_toolkit/waf_rules.py


# Category: SQL Injection (SQLi)
SQLI_PATTERNS = [
    r"(union\s*select)",
    r"(--|#|;)\s*$",
    r"(\s*or\s*\d+=\d+)",
    r"(and\s*(select|update|delete))",
    r"(benchmark\s*\()",
    r"(information_schema)",
]

# Category: Cross-Site Scripting (XSS)
XSS_PATTERNS = [
    r"<script.*?>",
    r"</script.*?>",
    r"(<|%3C)img\s+src\s*=\s*['\"]?\s*j\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t\s*:",
    r"on(error|load|click|mouseover|submit)\s*=",
    r"alert\s*\(",
    r"javascript:",
]

# Category: Path Traversal & Command Injection
INJECTION_PATTERNS = [
    r"\.\./", # ../
    r"\.\.\\", # ..\
    r"(etc/passwd)",
    r"(cmd\.exe)",
    r"(/bin/sh)",
]

ALL_PATTERNS = SQLI_PATTERNS + XSS_PATTERNS + INJECTION_PATTERNS