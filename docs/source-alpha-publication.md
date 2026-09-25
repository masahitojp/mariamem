# Source-only Go alpha publication checklist

This is the historical plan for `v0.1.0-alpha.1`. The upcoming
`v0.1.0-alpha.2` instructions are in [releasing](releasing.md).

Planned tag: `v0.1.0-alpha.1`. No publication command in this document was executed
as part of Task 5e. Native assets must not be attached.

## Target and checks

Tag the final Task 5e documentation commit (reported in the task completion),
which descends from `d00fd54`. That history includes:

- `0123ffa`: benchmark assets
- `6be76cc`: public Go API
- `20f527a`: real-guest integration
- `a78676b`: public module path
- `7bbd2af`: concurrent Fork and Close safety
- `d00fd54`: native candidate packaging infrastructure

The module lives at the repository root with module path
`github.com/masahitojp/mariamem`; a root tag `v0.1.0-alpha.1` is appropriate for
this v0 module. Do not add a subdirectory prefix or `/v0` import suffix.
Python's planned `0.1.0a1` version is independent.

Pre-tag requirements:

- Clean working tree and reviewed target commit; do not tag an unrelated later HEAD.
- Source checks and Go tests pass; all necessary code/docs are committed.
- No native binaries, wheel, secrets or local evidence files are tracked.
- Existing copyright/license/modified-work notices are retained.
- No local or remote `v0.1.0-alpha.1` tag already exists; never move a published tag.
- The target commit is pushed and its GitHub Source checks workflow succeeds.
- Read `release/GO-v0.1.0-alpha.1.md` and confirm source-only positioning.
- Leave release review flags and binary guards unchanged.

Task 5e remote inspection found the latest successful Source checks run at
`7bbd2af` ([run](https://github.com/masahitojp/mariamem/actions/runs/35893482779)).
The final documentation/packaging commit needs its own CI result after pushing.
The local `gh` login returned HTTP 401; reauthenticate if using optional CLI Release
creation. Public API access confirmed the CI result without altering credentials.

## Human publication commands (not executed)

Run from the public repository. First compare HEAD with the final Task 5e commit:

```sh
git status --short
git log -1 --oneline
git tag -l v0.1.0-alpha.1
git ls-remote --tags origin 'refs/tags/v0.1.0-alpha.1*'
```

Both tag checks must be empty. Push the reviewed source commit, then wait for its
Source checks workflow to succeed in GitHub Actions before proceeding:

```sh
git push origin main
```

With HEAD still on the reviewed Task 5e commit:

```sh
git tag -a v0.1.0-alpha.1 -m "mariamem v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

Optionally create a **source-only prerelease**, with no uploaded assets:

```sh
gh auth status
# If authentication is invalid, run gh auth login before continuing.
gh release create v0.1.0-alpha.1 \
  --repo masahitojp/mariamem --verify-tag --prerelease \
  --title 'mariamem v0.1.0-alpha.1 — source-only Go alpha' \
  --notes-file release/GO-v0.1.0-alpha.1.md
```

Do not add archive paths, SHA256SUMS, native candidates or wheels to this command.
GitHub's automatic repository source archives are expected. This procedure does
not approve or bypass binary publication checks.

## Post-tag consumer acceptance

Use Go 1.26 or newer in a new directory, without a local replace or parent go.work:

```sh
mkdir mariamem-alpha-smoke
cd mariamem-alpha-smoke
export GOWORK=off
go mod init example.com/mariamem-alpha-smoke
go get github.com/masahitojp/mariamem@v0.1.0-alpha.1
go list -m github.com/masahitojp/mariamem
```

The module version must report `v0.1.0-alpha.1`. Save this as `main.go`:

```go
package main

import (
    "context"
    "fmt"
    "os"
    "time"

    "github.com/masahitojp/mariamem"
)

func main() {
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    db, err := mariamem.Start(ctx, mariamem.Options{
        NativeDir: os.Getenv("MARIAMEM_NATIVE_DIR"),
    })
    if err != nil { panic(err) }
    fmt.Println(db.DSN())
    if err := db.Close(); err != nil { panic(err) }
}
```

Source/import acceptance does not need native artifacts:

```sh
go build .
```

Optional runtime smoke on the supported development platform requires an
**existing separately prepared native bundle, not provided by this release**:

```sh
MARIAMEM_NATIVE_DIR=/absolute/path/to/existing/native go run .
```

After source-only publication, address binary corresponding-source, notices and
platform blockers separately. A prerelease label does not resolve those checks.
