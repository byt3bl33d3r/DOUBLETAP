import pytest
from awsproxier import AWSProxier
from mitmproxy.test import tflow
from mitmproxy import http
from mitmproxy.net.http.headers import Headers

class MockApi:
    def __init__(self):
        self.proxies = {
            "api.hackertarget.com": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/gycsjh0/",
            "crt.sh": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/7au5iol/",
            "dnsdumpster.com": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/jfzw7lr/",
            "email-checker.net": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/s04n23z/",
            "hackertarget.com": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/b8pjr10/",
            "virustotal.com": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/9wejvax/",
            "www.virustotal.com": "https://4n6mt4wp35.execute-api.us-east-2.amazonaws.com/AWSProxier/7huj9rl/"
        }
"""
@pytest.mark.asyncio
async def test_create_response():
    f = tflow.tflow()
    p = AWSProxier()
    p.api = MockApi()

    p.load('')
    await p.create_response(f)
"""

def test_create_http_response():
    r = http.HTTPResponse.make(
        status_code=200,
        content=b'',
        headers={"Wat": "Wat"}
    )
    r.http_version = "1.1"
    r.reason = "OK"
    
    print(r)
    assert r == r
