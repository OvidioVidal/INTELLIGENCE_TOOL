from imapclient import IMAPClient
import email
import time
import re
import datetime as dt
from email.header import decode_header

# Change these depending on provider
IMAP_SERVER = "imap.gmail.com"
EMAIL_USER  = "ovidalreig@gmail.com"
EMAIL_PASS  = "wvvdngqubminnksz"
FOLDER      = "[Gmail]/All Mail"
SLEEP_SEC   = 3

# ---- Exact subject filter: only the (dd/mm/yyyy hh:mm:ss) part may vary ----
SUBJECT_FIXED_TEXT = "UK and German M&A Alert : MERGERMARKET"
SUBJECT_RE = re.compile(
    r'^' + re.escape(SUBJECT_FIXED_TEXT) + r' \(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\)$'
)

LOG_FILE = "auto_input_log.txt"

def dec(s):
    if not s:
        return ""
    out = []
    for text, enc in decode_header(s):
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", "replace"))
        else:
            out.append(text)
    return "".join(out)

def plain_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp  = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                b = part.get_payload(decode=True)
                if b:
                    return b.decode(part.get_content_charset() or "utf-8","replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                b = part.get_payload(decode=True)
                if b:
                    return b.decode(part.get_content_charset() or "utf-8","replace")
        return ""
    b = msg.get_payload(decode=True)
    return "" if not b else b.decode(msg.get_content_charset() or "utf-8","replace")

def subject_matches(msg):
    subj = dec(msg.get("Subject") or "").strip()
    return bool(SUBJECT_RE.match(subj)), subj

def save_to_file(msg):
    """Save only the latest email fully in input_email.txt"""
    from_ = dec(msg.get("From"))
    date_ = dec(msg.get("Date"))
    subj  = dec(msg.get("Subject"))
    body  = plain_text(msg) or ""
    with open("input_email.txt", "w", encoding="utf-8") as f:
        f.write(f"From: {from_}\nDate: {date_}\nSubject: {subj}\n\n{body}")
    print("[saved full email to input_email.txt]")

def log_event(message):
    """Append simple log line with timestamp."""
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(f"[{timestamp}] {message}\n")

def run():
    baseline = None
    seen = set()
    while True:
        try:
            with IMAPClient(IMAP_SERVER, ssl=True, timeout=60) as srv:
                srv.login(EMAIL_USER, EMAIL_PASS)
                info = srv.select_folder(FOLDER)
                baseline = info.get(b"UIDNEXT") or 1
                print(f"Connected. Watching {FOLDER}. Baseline UID: {baseline}.")
                log_event(f"Connected to {FOLDER} (Baseline UID {baseline})")

                while True:
                    uids = srv.gmail_search('newer_than:10m')
                    new_uids = [u for u in uids if u >= baseline and u not in seen]
                    if new_uids:
                        fetched = srv.fetch(new_uids, ['RFC822'])
                        for uid in sorted(new_uids):
                            raw = fetched[uid][b'RFC822']
                            msg = email.message_from_bytes(raw)
                            ok, subj_txt = subject_matches(msg)
                            if ok:
                                save_to_file(msg)
                                print(f"Matched subject: {subj_txt}")
                                log_event(f"Matched subject: {subj_txt}")
                            else:
                                log_event(f"Ignored subject: {subj_txt}")
                            seen.add(uid)
                        baseline = max(baseline, max(new_uids) + 1)

                    srv.noop()
                    time.sleep(SLEEP_SEC)
        except Exception as e:
            err_msg = f"Connection issue: {e} — retrying in 3s..."
            print(err_msg)
            log_event(err_msg)
            time.sleep(3)

if __name__ == "__main__":
    run()
