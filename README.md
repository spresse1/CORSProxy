# CORSProxy

## CI Status

Travis CI (master): [![Build Status](https://travis-ci.org/spresse1/CORSProxy.svg?branch=master)](https://travis-ci.org/spresse1/CORSProxy)
Codecov.io: [![codecov.io](https://codecov.io/github/spresse1/CORSProxy/coverage.svg?branch=master)](https://codecov.io/github/spresse1/CORSProxy?branch=master)

## Purpose

1. To proxy API requests.  This API either acts to proxy requests for a web_interface instance on the same host or adds the additional headers necessary for hosts somewhere else to make requests.
2. To add authentication.  This makes it suitable to expose to a wider network than merely your home, possibly allowing exposure to the internet.  Note that I still recommend not doing so and instead using SSH tunnels or a VPN to access the thermostat/web interface remotely.
3. To up- or downgrade encryption
4. To add CORS capabilities to APIs which currently do not support them.

Throughout an effort has been made to make security a primary goal.  This means that you should be able to configure this to allow as narrow a set of permissions as possible.

(This is somewhat ironic, given that the original goal of this was to circumvent a (misapplied) security measure)

## Use

To install, run the standard `python setup.py install`.  The installed package is CORSProxy, with a CORSProxy module and the Proxy class.  To use it, you probably want:
```
from CORSProxy.CORSProxy import Proxy
```

While I HIGHLY recommend setting this up under a proper WSGI server, an extremely simple invocation is:
```
>>> from CORSProxy.CORSProxy import Proxy
>>> from wsgiref.simple_server import make_server
>>> p = Proxy('localhost','8080')
>>> srv = make_server('localhost', 8081, p)
>>> srv.serve_forever()
```
which would create a proxy (which does nothing except pass through requests) listening on localhost:8081 and passing requests to localhost:8080.

## Testing
To test, run either:

1. `tox` (preferred)
2. `python setup.py test`

This module should have a 100% test coverage and tests are set to fail if this is not the case.

### Modifying tests

All tests are currently located in tests/ and (though untested) any tests using python's unittest module placed in this directory should run.


