CI42799185401 failed before any jobs started. actionlint1.7.7 reproduced the
error at workflow line68: runner context is unavailable in job-level env. The
reference path is now set in the consuming step's env, where runner is valid.
The same actionlint command passes after the change; no runtime code or data
oracle changed. Earlier YAML/bash syntax checks did not cover this expression
context rule. Use actionlint for subsequent changes to this workflow.
