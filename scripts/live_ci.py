#!/usr/bin/env python3
"""Validate complete manual Live acceptance; daily PR gates belong to Development."""
import argparse
import json
import os


def verify_gate(needs):
    assert set(needs) == {'native-reference', 'live'}, 'missing full acceptance dependency'
    for job in needs:
        assert needs[job]['result'] == 'success', job + ' did not complete full acceptance'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['gate'])
    parser.parse_args()
    verify_gate(json.loads(os.environ['NEEDS_JSON']))
    print('PASS: Live full acceptance gate')


if __name__ == '__main__':
    main()
