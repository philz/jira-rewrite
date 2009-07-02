#!/usr/bin/python
"""
Re-writes Apache's JIRA messages to remove JIRA's "Updated/Commented/Created" annotations,
as well as uniqueifying the from addresses.  This unbreaks Gmail's threading.

See also http://jira.atlassian.com/browse/JRA-3609

This file contains the common code; see rewritejira-imap and rewritejira-pipe
for actual use.
"""

import email
import email.Header # email.header in 2.5
import logging
import re
import sys

logger = logging.getLogger(__name__)

# Example subject line:
#   Subject: Re: [jira] Updated: (HADOOP-4675) Current Ganglia metrics skipped.
# Becomes:
#   Subject: Re: (HADOOP-4675) Current Ganglia metrics skipped.
# This captures the JIRA ticket number, but ignores the text in between.
SUBJECT_RE = re.compile(r"\[jira\](?: (?:[A-Za-z]+))+: (\([A-Z]+-[0-9]+\))", re.MULTILINE)
SUBJECT_REPLACE = "\\1"
# Example from:
#   From: "Joe Shmo Zeyliger (JIRA)" <jira@apache.org>
# Becomes:
#  From: "Joe Shmo (JIRA)" <Joe.Shmo.JIRA.@fake.jira.apache.org>
FROM_RE = re.compile('"(.*)" <jira@apache.org>', re.MULTILINE)
def from_replacement(m):
  if m.groups():
    fake_address = re.sub("[^a-zA-Z]+", ".", m.groups()[0]) + "@fake.jira.apache.org"
    return re.sub("jira@apache.org", fake_address, m.group())
  else:
    return m.group()

def rewrite_message(message_str):
  """Rewrites an entire message."""
  message = email.message_from_string(message_str)
  rewrite_message_header(message, "Subject", SUBJECT_RE, SUBJECT_REPLACE)
  rewrite_message_header(message, "From", FROM_RE, from_replacement)
  message["Reply-to"] = "jira@apache.org"
  return message.as_string()

def rewrite_message_header(message, header_name, regex, replacement):
  """Extracts header_name header from message and rewrites it."""
  h = message.get(header_name)
  if h:
    new_h = rewrite_header(h, regex, replacement)
    if new_h:
      logger.info("%s: %s -> %s", header_name, repr(h), repr(new_h))
      message.replace_header(header_name, new_h)
  return

def rewrite_header(header, regex, replacement):
  """
  Rewrites header by replaceing regex with replacement.

  Returns None if no changes can be made.
  This deals with annoying ("fancy") headers that look like "=?utf-8?Q?..." by
  calling out to email.header.
  """
  decoded_header = email.Header.decode_header(header)
  new_header = []
  total_subs = 0
  for (string, charset) in decoded_header:
    (newstring, num_subs) = regex.subn(replacement, string, 1)
    total_subs += num_subs
    new_header.append( (newstring, charset) )
  
  if total_subs:
    return email.Header.make_header(new_header).encode()
  else:
    return None
