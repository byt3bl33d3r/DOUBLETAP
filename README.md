# DOUBLETAP

<p align="center">
  <img src="https://media1.tenor.com/images/2ce301a35b13eea7b1e6d26a2ef98089/tenor.gif?itemid=12637269"/>
</p>

An asynchronous proxy to proxy HTTP traffic through [AWS API Gateway](https://aws.amazon.com/api-gateway/) and rotate IP address on each request.

## Sponsors
[<img src="https://www.blackhillsinfosec.com/wp-content/uploads/2016/03/BHIS-logo-L-300x300.png" width="130" height="130"/>](https://www.blackhillsinfosec.com/)
[<img src="https://handbook.volkis.com.au/assets/img/Volkis_Logo_Brandpack.svg" width="130" hspace="10"/>](https://volkis.com.au)
[<img src="https://user-images.githubusercontent.com/5151193/85817125-875e0880-b743-11ea-83e9-764cd55a29c5.png" width="200" vspace="21"/>](https://qomplx.com/blog/cyber/)
[<img src="https://user-images.githubusercontent.com/5151193/86521020-9f0f4e00-be21-11ea-9256-836bc28e9d14.png" width="250" hspace="20"/>](https://ledgerops.com)

## Table of Contents

- [DOUBLETAP](#doubletap)
  * [What is this?](#what-is-this)
  * [How does it work?](#how-does-it-work)
  * [Limitations](#limitations)
  * [Use Cases](#use-cases)
  * [OPSEC Considerations, Detection & Defense](#opsec-considerations-detections-defense)
  * [Installation](#installation)
    + [Docker](#docker)
    + [Source](#source)
  * [Usage](#usage)
    + [Starting the Proxy Using the Docker Image](#starting-the-proxy-using-the-docker-image)
    + [Starting the Proxy Using mitmproxy](#starting-the-proxy-using-mitmproxy)
    + [Sending Requests through the Proxy](#sending-requests-through-the-proxy)
  * [To Do](#to-do)

## What is this?

This is a [mitmproxy addon](https://docs.mitmproxy.org/stable/addons-overview/) that allows you to dynamically proxy HTTP traffic through [AWS API Gateway](https://aws.amazon.com/api-gateway/) in order to rotate IP address on each request.

Essentially, it's a fully weaponized version of the underlying concept which tools such as [FireProx](https://github.com/ustayready/fireprox) and the [IP_Rotate](https://github.com/RhinoSecurityLabs/IPRotate_Burp_Extension) Burp extension have implemented albeit with a *lot* major improvements:

- Written in Python 3
- Fully asynchronous (which is *extremely* important for this particular implementation to work efficiently)
- Works just like a regular proxy
- Dynamically creates, stages and deploys [AWS API Gateway](https://aws.amazon.com/api-gateway/) endpoints for each new domain across multiple AWS regions concurrently and transparently redirects traffic.

## How Does it Work?

[mitmproxy](https://mitmproxy.org/) exposes an [addon](https://docs.mitmproxy.org/stable/addons-overview/) system which allows you to create components of any complexity that interact with it's proxy engine.

When you first fire up DOUBLETAP, it'll query [AWS API Gateway](https://aws.amazon.com/api-gateway/) to see if there's already an existing API called "DOUBLETAP" (by default) which was previously setup by the tool, and if so pulls down a list of each API endpoint and the domains they proxy traffic to so that it doesn't create them again.

The real "magic" comes into play when you send an HTTP request through the proxy. DOUBLETAP works by hooking the mitmproxy `request` event, which fires every time the proxy receives a HTTP request, it then performs the following actions:

1. Constructs the root URL from the URL you requested
2. Checks an internal dictionary structure to see if it already setup an API Gateway endpoint that proxies traffic to that domain
3. If not, it'll concurrently create, stage and deploy a new API Geteway endpoint across multiple AWS regions ([10 by default](https://github.com/Porchetta-Industries/DOUBLETAP/blob/master/doubletap.py#L11)) to proxy traffic to the domain you requested (this makes the IP rotation rate is even higher).
4. During the API Gateway endpoint creation, it'll remap the `X-Forwarded-For` header: this allows us to specify an IP of our choosing that the end server will see in that header.
5. DOUBLETAP can detect when the API is fully staged (usually takes anywhere between 10-30 seconds) and will only allow the requests to proceed once the API endpoints are ready across all regions.
6. It'll then pick at random an API Gateway endpoint URL from the ones it created
7. Generate a fake IP for the `X-Forwarded-for` header and change the User Agent of the request
8. Finally it'll seamlessly redirect the modified request to the chosen API Gateway endpoint URL

The result is that the server you're hitting will see a truly unique IP on almost each request. Additionally it will not give away your real IP address through the `X-Forwarded-For` header as it's supplied a bogus IP.

What's super important to note here is that all of this happens **asynchronously** in the background, meaning the proxy does *not* block every time it has to interact with AWS and/or on each HTTP request.

## Limitations

A fundamental limitation of this technique/implementation is that whenever you request a URL to a new domain that DOUBLETAP *hasn't* created an API Gateway endpoint for previously, it takes anywhere between 10-30 seconds before the Gateway endpoint is staged and ready to accept traffic.

Practically speaking, this means an HTTP request to a new domain/URL will just sit there doing nothing for up to 30ish seconds until you receive back any data. Obviously, subsequent requests to that same domain/URL will not have this issue and you'll receive back the response instantly.

As far as I'm aware, there really isn't a way around this. Additionally, AWS doesn't provide a reliable way to determine whether an API Gateway endpoint has finished staging or not. DOUBLETAP handles this by spinning up background AsyncIO tasks that perform an HTTP request to the endpoint URLs and do a [signature check](https://github.com/Porchetta-Industries/DOUBLETAP/blob/master/doubletap/aws.py#L403-L421) on the response looking for specific status codes and data that I've found through testing mean the API is still staging.

To help alleviate this limitation, I'll be implementing "domain pre-loads" and "domain allow/deny" lists/regexes. This should help *a lot* when proxying headless browsers through DOUBLETAP for example.

Additionally:

- HTTP/2 requests are not supported. [mitmproxy](https://mitmproxy.org/) doesn't have the ability to redirect HTTP/2 connections (yet). However, AWS API Gateway does support HTTP/2 and Websocket connections so mitmproxy just needs to catch up.
- Incredibly, if the end service you're trying access uses legitimately uses AWS API Gateway, the proxying won't work. It's like a cloud Judo move. Thankfully, not a lot of things use AWS API Gateway as I've only ran into this once in a year or so of using this.

## Use Cases

1. The new SprayingToolkit update is built to support proxying everything through DOUBLETAP. No more IP blacklisting 😈
2. ENTROPICFORESIGHT is built to support proxying everything through DOUBLETAP. No more API keys and/or rate limiting when trying to scrape OSINT data 😈
2. Scraping with Headless Browsers, this will work a lot better once I implement the "domain pre-loads" and the domain allow/deny lists.
3. Anything that can benefit from a new IP on each request 😈 make the possibilities flow through you.

## OPSEC Considerations, Detection & Defense


### Offensive OPSEC Considerations

- The underlying technique can be detected by looking for the `x-amz-apigw-id` header which is sent on each request through AWS API Gateway. There is no way to avoid this. (See the [Defense & Detection](#defense-&-detection) section for more details)
- While the IP on each request does change *most* of the time there is always a slight possibility it doesn't as this isn't a "legit" feature of AWS API Gateway. Either way, your real IP won't ever be revealed.

### Defense & Detection

While the IP address does change on each connection, there are some things that are "baked" into how AWS API Gateway works that can be used to detect this technique.

**Note: all of the below is from my current understanding of how things work which is subject to change 😜. I'm by no means an AWS expert. Feel free to reach out if something is inaccurate.**

The most effective way of identifying the *underlying technique* of this tool (this is a non-fragile detection) is to look for the `x-amz-apigw-id` header in HTTP requests. This header contains a Base64 encoded value which identifies the API Gateway being used and there isn't a way to overwrite it/remove it (unlike the `X-Forwarded-For` header). This can be used to identify the AWS account which has deployed the specific gateway, so you could give the header value to AWS in order to file an abuse complaint if needed.

You probably shouldn't be receiving HTTP requests from AWS API Gateway anyway so I feel pretty confident in saying this is safe way of blocking/detecting this technique. Creating an IDS/IPS rule looking for that header should be pretty trivial.

If you're using AWS API Gateway legitimately to host your service in the first place, you're implicitly safe from this technique as proxying to another service hosted on AWS API Gateway won't work! I call this a cloud Judo.

## Installation

### Docker

```console
docker build github.com/Porchetta-Industries/DOUBLETAP
```

### Source

```console
git clone https://github.com/Porchetta-Industries/DOUBLETAP && cd DOUBLETAP
pip3 install -r requirements.txt
```

## Usage

DOUBLETAP needs AWS credentials in order to interact with AWS API Gateway. By default it'll look for the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables containing the AWS access key and AWS secret key respectively. If it doesn't find those environment variables, it'll try to grab access and secret key from the `~/.aws/credentials` file which is setup when you install the [AWS CLI utility](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html).

The proxy will bind on all interfaces on port `8080` by default.

### Starting the Proxy Using the Docker Image

```console
docker run -p 8080:8080 -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY --rm -it $IMAGE_ID
```

### Starting the Proxy Using mitmproxy

```console
mitmdump -v --no-http2 -k -s doubletap.py
```

### Sending Requests through the Proxy

This really comes down to what you're trying to do/tool you're using. Generally, most tools have HTTP proxy support. You can also use ProxyChains to "force" something to use a proxy.

Here's some commands I recommend trying to test the proxy is working and to get an idea how things work:

**Note: please read the [limitations](#limitations) section. First time you request a URL/domain it can take up to 30 seconds to receive back a response. Depending on the tool, you might need to set a higher timeout threshold in order to accommodate this.**

#### cURL:
```console
curl --insecure -x http://127.0.0.1:8080 -v https://ifconfig.me/all
```

#### HTTPie:
```console
http --verify no -v --proxy http://127.0.0.1:8080 https://ifconfig.me/all
```

If you run one of the above commands, you should see a new IP in the response on each request 🔥😈

# To Do

- Implement "domain/URL pre-loads"
- Implement "domain/URL allow/deny" support with regexes
- Allow customization of how DOUBLETAP chooses the API Gateway proxy URL (e.g. Round-Robin as supposed to at random)
- Allow customization of User-Agent replacement.
- Allow customization of how the bogus IP in the `X-Forwarded-For` header is generated
- Expose a "cleanup" command to remove stages from API Gateway
- Better logging