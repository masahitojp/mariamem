"""Source SDK Live smoke using the already-built integration host, no browser/wheel."""
import argparse
import json
import mariamem
from installed_python import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    args = parser.parse_args()
    print(json.dumps(dict(result='PASS_SOURCE_PYTHON_LIVE',
                         **check(mariamem.start(host_binary=args.host)))))


if __name__ == '__main__':
    main()
