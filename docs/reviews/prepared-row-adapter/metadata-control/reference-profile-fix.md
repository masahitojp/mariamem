# CI42800472278: native reference profile unavailable

The workflow parsed, but its Linux/Python3.14 native-reference job could not load
Connector26.7.0's C extension. actual-guest was consequently skipped. This is not
a new observed guest SQL failure. The environment is now recorded by the existing
connector environment diagnostic without patching SSL/imports or silently using
the pure implementation in place of C extension.

Native CI now owns only the complete raw-wire before/after oracle using PyMySQL.
Guest must still match every packet and changed column count. Its C-extension
path remains use_pure=False and is compared to the preserved native macOS/
Python3.11 observation, including exact2057. This is explicitly a different Python
minor from CI's macOS3.14, not a same-profile native C-extension certification.
The guest observation is retained as a separate artifact. Full consumer-profile
qualification remains with#132; it is not newly completed here.

Locally, the fixed native12.3.3 server was tested with Connector.connect made
unavailable in the test process: wire-only observation still matched all saved
native metadata/status/row bytes, while requesting the C-extension path raised
ImportError without fallback. An initial connection before server readiness
failed; the successful check followed explicit mariadb-admin ping. CI already
uses service health checking. Product code and wire expectations are unchanged.
