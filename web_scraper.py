#!/usr/bin/env python3
"""Web Scraper MCP Server - provides web scraping tools for the agent"""

import json
import sys
import urllib.request
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    """Extract plain text from HTML, skipping scripts/styles."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True
    
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False
    
    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.text_parts.append(text)
    
    def get_text(self):
        return "\n".join(self.text_parts)


class LinkExtractor(HTMLParser):
    """Extract all links from HTML."""
    def __init__(self):
        super().__init__()
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, val in attrs:
                if attr == 'href' and val:
                    self.links.append(val)


def fetch_url(url: str) -> str:
    """Fetch raw HTML from a URL."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
            return html[:50000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


def get_text(url: str) -> str:
    """Fetch a URL and extract plain text content."""
    html = fetch_url(url)
    if html.startswith("Error"):
        return html
    try:
        parser = TextExtractor()
        parser.feed(html)
        return parser.get_text()[:10000]
    except Exception as e:
        return f"Error extracting text: {e}"


def get_links(url: str) -> str:
    """Fetch a URL and extract all hyperlinks."""
    html = fetch_url(url)
    if html.startswith("Error"):
        return html
    try:
        parser = LinkExtractor()
        parser.feed(html)
        links = parser.links
        return "\n".join(links[:50])
    except Exception as e:
        return f"Error extracting links: {e}"


def handle_request(request_data):
    """Handle an incoming MCP request."""
    method = request_data.get("method")
    
    if method == "initialize":
        return {
            "serverInfo": {
                "name": "web-scraper",
                "version": "1.0.0"
            }
        }
    
    elif method == "tools/list":
        return {
            "tools": [
                {
                    "name": "fetch_url",
                    "description": "Fetch raw HTML from a URL"
                },
                {
                    "name": "get_text",
                    "description": "Fetch a URL and extract plain text content"
                },
                {
                    "name": "get_links",
                    "description": "Fetch a URL and extract all hyperlinks"
                }
            ]
        }
    
    elif method == "tools/call":
        tool_name = request_data.get("params", {}).get("name")
        tool_args = request_data.get("params", {}).get("arguments", {})
        
        if tool_name == "fetch_url":
            result = fetch_url(tool_args.get("url", ""))
        elif tool_name == "get_text":
            result = get_text(tool_args.get("url", ""))
        elif tool_name == "get_links":
            result = get_links(tool_args.get("url", ""))
        else:
            result = f"Unknown tool: {tool_name}"
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": result
                }
            ]
        }
    
    return {"error": f"Unknown method: {method}"}


def main():
    """Main server loop - read requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON decode error: {e}"}))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
