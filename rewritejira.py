#!/usr/bin/env python2.5
"""
Re-writes JIRA subject lines to remove JIRA's "Updated/Commented/Created" annotations.
JIRA's default subjects break Gmail's threading (which threads by subject line); making the
subject line uniform unbreaks Gmail's threading.

Specifically, this looks at every message in --source, does a search and replace
with --regex and --replace (defaults are for JIRA subject lines), and puts the
modified message in --dest.  The original message is moved to --backup.
"""
# FEATURES:
#  * GMail's internal dates are preserved, so messages are dated and sorted according
#    to their original arrival.
# 
# BUGS:
#  * I believe Google throttles the IMAP requests.  Probably possible to use fancier
#    IMAP to batch these guys.
#  * Every once in a while you'll see:
#   AssertionError: Error: ('NO', ['Unable to append message to folder (Failure)'])
#    I think this happens when you're concurrently accessing your inbox (or possibly
#    mail is getting delivered).  For now, retry.
# 
# REFERENCES:
#  * RFC 2060 has the IMAP spec.
#  * http://docs.python.org/library/email.header.html explains the "?=UTF-8" nonsense
#    you sometimes see in headers.  Unintuitively, rfc822 or mimetools are pretty
#    much superceded by the email package.
#  * imapsync (http://www.linux-france.org/prj/imapsync/README) has some of this
#    functionality, and is more generic.
#
# EXAMPLE OUTPUT:
#   $ python rewritejira.py --username ...@....com --source hadoop-jira --dest hadoop-jira-rewritten --backup hadoop-jira-orig
#   Password: 
#   INFO:__main__:Looking at 3 messages.
#   INFO:__main__:[3] Subject: '[jira] Commented: (HADOOP-5649) Enable ServicePlugins for the\r\n JobTracker' -> '(HADOOP-5649) Enable ServicePlugins for the\r\n JobTracker'
#   INFO:__main__:[2] Subject: '[jira] Commented: (HADOOP-5581) libhdfs does not get\r\n FileNotFoundException' -> '(HADOOP-5581) libhdfs does not get\r\n FileNotFoundException'
#   INFO:__main__:[1] Subject: '[jira] Commented: (HADOOP-5638) More improvement on block placement\r\n performance' -> '(HADOOP-5638) More improvement on block placement\r\n performance'
#   INFO:__main__:Rewrote 3 messages.

import email
import email.header
import getpass
import imaplib
import logging
import optparse
import re
import time

logger = logging.getLogger(__name__)

# Example subject line:
#   Subject: Re: [jira] Updated: (HADOOP-4675) Current Ganglia metrics skipped.
# This captures the JIRA ticket number, but ignores the text in between.
DEFAULT_RE = r"\[jira\](?: (?:[A-Za-z]+))+: (\([A-Z]+-[0-9]+\))"
DEFAULT_REPLACE = "\\1"

def check(arg):
  """imaplib functions tend to return (OK, foo).  This checks the OK and returns foo."""
  status, rest = arg
  assert status == "OK", "Error: " + str(arg)
  return rest

def login(server, user, password):
  """Connect to IMAP server with credentials."""
  i = imaplib.IMAP4_SSL(server)
  check(i.login(user, password))
  return i

def logout(client):
  """Close client."""
  client.close()
  client.logout()

def select_mailbox(client, mailbox):
  """Selects mailbox."""
  client.select(mailbox)

def query(client):
  """Queries for messages with subject containing [jira] in selected mailbox."""
  m = check(client.search(None, 'SUBJECT', '[jira]'))[0]
  if not m:
    return []
  # The id numbers tend to come in ascending order.  We reverse
  # the order so that we go oldest first.
  return reversed(m.split(" "))

def parse_message_fetch(ret):
  """Extracts date, flags, and message from a message.fetch.
  
  Quite probably this is gmail-specific, and not agnostic to the IMAP server.
  """
  # Get the message
  if not ret[0]:
    raise Exception("Error: " + str(ret))
  if "RFC822" not in ret[0][0]:
    raise Exception("Error: " + str(ret))
  message = ret[0][1]

  # Sample flagsdate: ' INTERNALDATE "16-Dec-2008 15:55:11 +0000" FLAGS (\\Seen Old))'
  flagsdate = ret[1]
  assert "FLAGS" in flagsdate
  assert "INTERNALDATE" in flagsdate

  # Extract flags (messy).  e.g., "FLAGS (Old))" -> "(Old)"
  flags = re.search("FLAGS (\(.*\))\)", flagsdate).groups()[0]

  # Extract internal date
  date = re.search('INTERNALDATE ("[^"]*")', flagsdate).groups()[0]

  return message, flags, date

def rewrite(client, message_id, regex, replacement, dest, backup, dryrun):
  """
  Fetches a message, and rewrites subject line according to regex and replacement.
  
  Returns 1 if message was rewritten; 0 otherwise.
  """
  ret = check(client.fetch(message_id, '(FLAGS RFC822 INTERNALDATE)'))
  if not ret[0]:
    logger.warning("Message_id %d empty." % message_id)
    return 0

  message_str, flags, date = parse_message_fetch(ret)
  message = email.message_from_string(message_str)
  subject = message.get("Subject")
  if not subject:
    logger.warning("Message_id %d, empty subject." % message_id)
    return 0

  new_subject = rewrite_subject(subject, regex, replacement)
  if new_subject:
    logger.info("[%d] Subject: %s -> %s", message_id, repr(subject), repr(new_subject))
    if dryrun:
      return 0

    message.replace_header("Subject", new_subject)

    # Store the new one first, so that if we fail, we can pick up where we left off.
    # (Gmail doesn't mind duplicate stores.)
    check(client.append(dest, flags, date, message.as_string()))

    # Move the original to hadoop-jira-orig
    check(client.copy(message_id, backup))

    # Delete the current one
    check(client.store(message_id, '+FLAGS', '\\Deleted'))
    check(client.expunge())
    return 1

  logger.warning("Message_id %d, subject %s skipped." % (message_id, subject))
  return 0

def rewrite_subject(subject, regex, replacement):
  """
  Rewrites subject by replaceing regex with replacement.

  Returns None if no changes can be made.
  This deals with annoying headers that look like "=?utf-8?Q?..." by
  calling out to email.header.
  """
  decoded_subject = email.header.decode_header(subject)
  new_subject = []
  total_subs = 0
  for (string, charset) in decoded_subject:
    (newstring, num_subs) = regex.subn(replacement, string, 1)
    total_subs += num_subs
    new_subject.append( (newstring, charset) )
  
  if total_subs:
    return email.header.make_header(new_subject).encode()
  else:
    return None

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)

  parser = optparse.OptionParser(usage=
    "%prog --username <username> --source <source_folder> " +
    "--dest <dest_folder> --backup <backup_folder> [--help] [--dryrun] [other_options]",
    epilog=__doc__)

  parser.add_option("--source", help="Folder whose messages to rewrite.  Folder (label) must already exist.")
  parser.add_option("--dest", help="Folder to save rewritten messages.  Folder (label) must already exist.")
  parser.add_option("--backup", help="Folder where to save originals.  Folder (label) must already exist.")

  parser.add_option("--regex", default=DEFAULT_RE, help="Regexp to match.  Default: %default")
  parser.add_option("--replace", default=DEFAULT_REPLACE, help="Replacement.  Default: %default")

  parser.add_option("--dryrun", action="store_true", default=False, help="Print out what would be done.")
  parser.add_option("--pwfile", help="File storing password.")
  parser.add_option("--imapserver", default="imap.gmail.com", help="IMAP server.  Default: %default")
  parser.add_option("--username", help="Username")
  parser.add_option("--loop", action="store_true", help="Loop mode.  Run every 5 minutes.")
  parser.add_option("--sleep", type=int, default=5*60, help="Sleep time between runs in loop mode.  Default: %default seconds.")
  (options, args) = parser.parse_args()
  if args:
    parser.error("Unexpected arguments: " + str(args))

  for p in ("source", "dest", "backup", "username"):
    if not getattr(options, p):
      parser.error("--%s is required" % p)

  if options.pwfile:
    password = file(options.pwfile).read().rstrip()
  else:
    password = getpass.getpass()

  first = True
  while first or options.loop:
    first = False
    try:
      client = login(options.imapserver, options.username, password)
      select_mailbox(client, options.source)
      regex = re.compile(options.regex, re.MULTILINE)

      message_ids = query(client)
      logger.info("Looking at %d messages." % len(message_ids))

      count = 0
      for m in message_ids:
        count += rewrite(client, int(m), regex, options.replace, options.dest, options.backup, options.dryrun)

      logout(client)
      logger.info("Rewrote %d messages." % count)
    except Exception, e:
      logger.exception("Exception during processing.")
    if options.loop:
      logger.info("Sleeping for %d seconds." % options.sleep)
      time.sleep(options.sleep)
