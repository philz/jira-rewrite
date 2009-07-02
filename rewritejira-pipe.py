#!/usr/bin/python
"""
Rewrites messages coming in via stdin.  See rewritejira.py.
"""

from rewritejira import rewrite_message

if __name__ == "__main__":
  # logging.basicConfig(level=logging.INFO)
  print rewrite_message(sys.stdin.read())
