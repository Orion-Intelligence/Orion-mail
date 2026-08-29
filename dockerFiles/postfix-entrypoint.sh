#!/bin/sh
set -e

MAIL_DOMAIN="${MAIL_DOMAIN:-mail.orionintelligence.org}"
POSTFIX_MYNETWORKS="${POSTFIX_MYNETWORKS:-127.0.0.0/8 172.16.0.0/12}"
POSTFIX_MILTER="${POSTFIX_MILTER:-inet:rspamd:11332}"
POSTFIX_MESSAGE_SIZE_LIMIT="${POSTFIX_MESSAGE_SIZE_LIMIT:-67108864}"

cp -a /etc/postfix.template/. /etc/postfix/
cp -a /etc/aliases /etc/postfix/aliases
chown postfix:postfix /var/lib/postfix

postconf -e "myhostname = ${MAIL_DOMAIN}"
postconf -e "mydestination = localhost"
postconf -e "inet_interfaces = all"
postconf -e "inet_protocols = ipv4"
postconf -e "virtual_mailbox_domains = ${MAIL_DOMAIN}"
postconf -e "virtual_transport = orion-mail"
postconf -e "mynetworks = ${POSTFIX_MYNETWORKS}"
postconf -e "smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination"
postconf -e "message_size_limit = ${POSTFIX_MESSAGE_SIZE_LIMIT}"
postconf -e "alias_maps = hash:/etc/postfix/aliases"
postconf -e "alias_database = hash:/etc/postfix/aliases"
postconf -e "maillog_file = /dev/stdout"
postconf -e "smtpd_milters = ${POSTFIX_MILTER}"
postconf -e "non_smtpd_milters = ${POSTFIX_MILTER}"
postconf -e "milter_default_action = accept"
postconf -e "export_environment = TZ MAIL_CONFIG LANG ORION_MAIL_INCOMING_URL ORION_MAIL_INCOMING_TOKEN"
postconf -F "*/*/chroot = n"
postconf -M "orion-mail/unix=orion-mail unix - n n - - pipe flags=Rq user=orionmail argv=/usr/local/bin/python3 /opt/orion-mail/backend/postfix_incoming_handler.py \${recipient}"

newaliases
postfix check || true

exec postfix start-fg
