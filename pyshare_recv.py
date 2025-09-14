#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse


def list_files(url: str):
    r = requests.get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    files = []
    for a in soup.find_all("a"):
        href = a.get('href')
        if href and not href.endswith('/'):
            files.append((a.text.strip(), href))
    return files


def download_file(base: str, href: str, dest: str = '.'):
    url = urljoin(base, href)
    local_name = os.path.basename(urlparse(url).path)
    r = requests.get(url, stream=True)
    r.raise_for_status()
    path = os.path.join(dest, local_name)
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    return path


def main():
    print("PyShare Receiver")
    url = input("Sender base URL (e.g. http://1.2.3.4:8000/): ").strip()
    if not url:
        return
    try:
        files = list_files(url)
    except Exception as e:
        print("Failed to list files:", e)
        return
    if not files:
        print("No files found at the URL")
        return
    print("Files:")
    for i, (name, href) in enumerate(files, 1):
        print(f"{i}: {name}")
    print("Enter numbers separated by space to download, or 'all'")
    choice = input("> ").strip()
    to_download = []
    if choice.lower() == 'all':
        to_download = files
    else:
        idxs = []
        for part in choice.split():
            try:
                idxs.append(int(part) - 1)
            except Exception:
                pass
        for i in idxs:
            if 0 <= i < len(files):
                to_download.append(files[i])
    for name, href in to_download:
        print(f"Downloading {name}...")
        try:
            path = download_file(url, href)
            print(f"Saved to {path}")
        except Exception as e:
            print(f"Failed to download {name}: {e}")


if __name__ == '__main__':
    main()
