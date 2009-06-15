These scripts re-write JIRA messages to remove JIRA's
"Updated/Commented/Created" annotations.  The "pipe" version also uniqueify the
from addresses.  This unbreak's Gmail's threading.

See http://jira.atlassian.com/browse/JRA-3609 for more color.

The IMAP Version
================

I use something like:
  rewritejira-imap.py --username philip@cloudera.com --source avro --dest avro --backup hadoop-jira-orig --pwfile /Volumes/EncryptedDisk/mypassword --loop
running in the background to rewrite a mailing list.


The Pipe Version
================

If you have procmail, you can filter the messages with rewritejira-pipe.py.  In my case, I've set up a 
shadow mailing list for core-dev.

1) Create a new mailing list with ezmlm.  "tarsier" happens to be my (virtual) domain name.

ezmlm-make -m -0 core-dev@hadoop.apache.org \
  ~/hadoop-core-dev-rewrite \
  ~/.qmail-tarsier-hadoop-core-dev-rewrite \
  hadoop-core-dev-rewrite tarsier.net

-m makes it moderated; -0 makes it a sublist of the original list.

2) Create a special target.  In my case, I configured
".qmail-tarsier-hadoop-core-dev-rewrite-XXXXX" to contain:

|/home/philz/hadoop-core-dev-rewrite/rewrite-pipe.py | /usr/local/bin/ezmlm/ezmlm-send '/home/philz/hadoop-core-dev-rewrite'
|/usr/local/bin/ezmlm/ezmlm-warn '/home/philz/hadoop-core-dev-rewrite' || exit 0
/home/philz/HADOOP_TEMPORARY # delete this in a later step

3) I subscribed myself to the core-dev mailing list.  Hand-written SMTP follows.
Note that I looked at the HADOOP_TEMPORARY box to find the subscribe confirmation.

  $telnet mx1.us.apache.org 25
  Trying 140.211.11.136...
  Connected to mx1.us.apache.org.
  Escape character is '^]'.
  220 apache.org ESMTP qpsmtpd 0.29 ready; send us your mail, but not your spam.
  HELO tarsier.net
  250 apache.org Hi [64.15.164.123] [64.15.164.123]; I am so happy to meet you.
  MAIL FROM:<hadoop-core-dev-rewrite-XXXXX@tarsier.net>
  250 <hadoop-core-dev-rewrite-XXXXX@tarsier.net>, sender OK - how exciting to get mail from you!
  RCPT TO:<core-dev-subscribe@hadoop.apache.org>
  250 <core-dev-subscribe@hadoop.apache.org>, recipient ok
  DATA
  354 go ahead
  From: hadoop-core-dev-rewrite-XXXXX@tarsier.net
  To: core-dev-subscribe@hadoop.apache.org
  Subject: Subscribe

  250 Queued!  (Queue-Id: 48BFD7248B8)

  220 apache.org ESMTP qpsmtpd 0.29 ready; send us your mail, but not your spam.
  HELO tarsier.net
  250 apache.org Hi [64.15.164.123] [64.15.164.123]; I am so happy to meet you.
  MAIL FROM:<hadoop-core-dev-rewrite-XXXXX@tarsier.net>
  250 <hadoop-core-dev-rewrite-XXXXX@tarsier.net>, sender OK - how exciting to get mail from you!
  RCPT TO:<core-dev-sc.1245025609.YYYYYYYY-hadoop-core-dev-rewrite-XXXXX=tarsier.net@hadoop.apache.org>
  250 <core-dev-sc.1245025609.hjkgmbidhfogedbpjllb-hadoop-core-dev-rewrite-XXXXX=tarsier.net@hadoop.apache.org>, recipient ok
  DATA
  354 go ahead
  From: hadoop-core-dev-rewrite-XXXXX@tarsier.net
  To: core-dev-sc.1245025609.YYYYYYYY-hadoop-core-dev-rewrite-XXXXX=tarsier.net@hadoop.apache.org

  250 Queued! ...

4) Remove the HADOOP_TEMPORARY line from your ezmlm alias.

5) Subscribe by e-mailing hadoop-core-dev-rewrite-subscribe@tarsier.net
