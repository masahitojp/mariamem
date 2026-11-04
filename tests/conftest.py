# Historical campaigns and optional resource-meter controls have explicit owners.
# Explicit paths remain runnable: pytest tests/measurement or pytest tests/native.
# Release's full check invokes tests/native separately; daily checks do not compile C.
collect_ignore = ["historical", "measurement", "native"]
