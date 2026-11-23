"""Keep the guest entropy namespace independent of the host OS filesystem."""
CHANGES = (
    ('\t"fmt"\n', '\t"fmt"\n\t"github.com/masahitojp/mariamem/internal/entropyfs"\n'),
    ('return os.Open("/" + strings.TrimPrefix(name, "/"))',
     'return entropyfs.Open("/" + strings.TrimPrefix(name, "/"))'),
    ('return os.Stat("/" + strings.TrimPrefix(name, "/"))',
     'return entropyfs.Stat("/" + strings.TrimPrefix(name, "/"))'),
)


def apply(name, text):
    if name != 'main.go':
        return text
    for old,new in CHANGES:
        if text.count(old) != 1:
            raise ValueError('host entropy preimage changed: ' + old)
        text=text.replace(old,new,1)
    return text
