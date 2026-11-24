"""Bounded public-page acquisition for the editorial Noticias desk."""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_BYTES = 2_000_000


def public_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Podaj pełny adres HTTP lub HTTPS bez spacji.')
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {'http', 'https'} or not host or parsed.username or parsed.password:
            raise ValueError
        if parsed.port not in {None, 80, 443}:
            raise ValueError
        if host.lower() in {'localhost', 'metadata.google.internal'} or host.lower().endswith(('.local', '.internal', '.localhost')):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and not address.is_global:
            raise ValueError
    except ValueError:
        raise ValueError('Użyj publicznej strony HTTP/HTTPS, bez danych logowania i niestandardowego portu.') from None
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or '/', parsed.query, ''))


def public_address(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
        raise ValueError('Źródło wskazuje adres prywatny lub lokalny.')
    return addresses[0][4][0]


class PinnedHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.create_connection((public_address(self.host, self.port), self.port), self.timeout)


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        sock = socket.create_connection((public_address(self.host, self.port), self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def fetch_page(value):
    """Validate every redirect and connect to the validated IP, retaining TLS SNI."""
    current = public_url(value)
    for _ in range(5):
        parsed = urlsplit(current)
        connection = (PinnedHTTPS if parsed.scheme == 'https' else PinnedHTTP)(parsed.hostname, port=parsed.port, timeout=12)
        try:
            connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers={
                'User-Agent': 'CanariasCercaEditorial/1.0',
                'Accept': 'text/html,application/rss+xml,application/atom+xml,application/xml',
                'Accept-Encoding': 'identity',
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader('Location')
                if not location:
                    raise ValueError('Źródło zwróciło przekierowanie bez adresu.')
                current = public_url(urljoin(current, location))
                continue
            if response.status != 200:
                raise ValueError(f'Źródło zwróciło HTTP {response.status}. Możesz wkleić materiał ręcznie.')
            content_type = response.getheader('Content-Type', '').lower()
            if not any(t in content_type for t in ('html', 'xml')):
                raise ValueError('Źródło musi być stroną HTML albo kanałem RSS/Atom.')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Strona przekracza limit 2 MB. Wklej potrzebny fragment ręcznie.')
            return {'url': current, 'html': raw, 'content_type': content_type}
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            raise ValueError('Nie można pobrać strony. Sprawdź link albo wklej materiał ręcznie.') from exc
        finally:
            connection.close()
    raise ValueError('Źródło ma zbyt wiele przekierowań.')
