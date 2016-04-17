#!/usr/bin/env python

"""
Tests to cover the CORSProxy.Proxy class.
"""

# Unit testing is good for the soul.
import mock
import unittest
from CORSProxy.CORSProxy import Proxy

banned_headers = [
      ("Connection", "My-Value"),
      ("Keep-Alive", "False"),
      ("Proxy-Authenticate", "Nope"),
      ("Proxy-Authorization", "Not here"),
      ('TE', "what"),
      ('Trailers', "None"),
      ('Transfer-Encoding', "Nothing"),
      ('Upgrade', "Dont"),
    ]


class Response:
    """
    A simple wrapper to keep track of response details.
    """
    status = ""
    headers = []
    environ = {}


def get_default_environ():
    """
    Fetches an approximation of the environment object used by WSGI servers.
    """
    return {
            "GATEWAY_INTERFACE": 'CGI/1.1',
            "HTTP_ACCEPT": '*/*',
            "HTTP_HOST": 'localhost:80',
            "HTTP_USER_AGENT": 'curl/7.47.0',
            "PATH_INFO": '/',
            "QUERY_STRING": '',
            "REMOTE_ADDR": '127.0.0.1',
            "REMOTE_HOST": 'localhost',
            "REQUEST_METHOD": 'GET',
            "SCRIPT_NAME": '',
            "SERVER_NAME": 'localhost',
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": 'HTTP/1.1',
            "SERVER_SOFTWARE": 'WSGIServer/0.1 Python/2.7.11+',
            "wsgi.multiprocess": False,
            "wsgi.multithread": True,
            "wsgi.run_once": False,
            "wsgi.url_scheme": 'http',
            "wsgi.version": (1, 0),
           }


class test_CORSProxy(unittest.TestCase):
    """
    A class encompasing tests for the CORSProxy.Proxy class
    """
    def simulate_called(self, environ, start_response):
        """
        Simulates the side effects of calling the wsgiproxy.exactproxy class.
        Mostly this is just storing the environment.
        """
        self.response.environ = environ
        start_response(self.status, self.headers)
        return mock.DEFAULT

    def simulate_start_response(self, status, headers):
        """
        Simulates the start_response function.  Stores the status and headers
        passed to it.
        """
        self.response.status = status
        self.response.headers = headers

    def setUp(self):
        """
        See unittest module for more details.  Generic setup for every test.
        """
        self.environ = None
        self.headers = []
        self.status = "200 OK"
        self.response = Response()
        self.mf = mock.patch('CORSProxy.CORSProxy.proxy_exact_request').start()
        self.mf.return_value = "Success!"
        self.mf.side_effect = self.simulate_called
        self.cp = Proxy('localhost')

    def test_basic(self):
        """
        Tests basic functionality of the class and test harness.  The simplest
        possible code path.
        """
        res = self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(res, "Success!")
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
        self.assertEquals(self.response.status, "200 OK")

    def test_auth_true(self):
        """
        Tests that authentication behaves as intended when the passed auth
        function returns True
        """
        self.cp = Proxy('localhost', auth=lambda x: True)
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEqual(self.response.status, "200 OK")

    def test_auth_false(self):
        """
        Tests that authentication behaves as expected (returns 401) when the
        authentication functon returns False
        """
        self.cp = Proxy('localhost', auth=lambda x: False)
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEqual(self.response.status, "401 Unauthorized")

    def test_auth_message(self):
        """
        Tests that authentication behaves as expected (returns 401 and an error
        string) when the authentication function returns a string.
        """
        self.cp = Proxy('localhost',
                        auth=lambda x: "My error message")
        res = self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEqual(self.response.status, "401 Unauthorized")
        self.assertEqual(res, "My error message")

    def test_keep_https(self):
        """
        Verifies that the https protocol is maintained when the request used it
        and the user did not specify a target_protocol
        """
        env = get_default_environ()
        env['wsgi.url_scheme'] = "https"
        env['HTTPS'] = "on"
        res = self.cp(env, self.simulate_start_response)
        self.assertEquals(res, "Success!")
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "https")
        self.assertEquals(self.response.environ['HTTPS'], "on")

    def test_keep_http(self):
        """
        Verifies that the http protocol is maintained when the request used it
        and the user did not specify a target_protocol
        """
        env = get_default_environ()
        res = self.cp(env, self.simulate_start_response)
        self.assertEquals(res, "Success!")
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
        self.assertNotIn('HTTPS', self.response.environ)

    def test_force_http_downgrade(self):
        """
        Tests that the request is downgraded to http if the incoming request
        was https and the user specified target_protocol=http
        """
        self.cp = Proxy('localhost', target_protocol="http")
        env = get_default_environ()
        env['wsgi.url_scheme'] = "https"
        env['HTTPS'] = "on"
        res = self.cp(env, self.simulate_start_response)
        self.assertEquals(res, "Success!")
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
        self.assertEquals(self.response.environ['SERVER_PORT'], "80")
        self.assertNotIn('HTTPS', self.response.environ)

    def test_force_https_upgrade(self):
        """
        Tests that the request is upgraded to https is the incoming request
        was http and the user specified target_protocol=https
        """
        self.cp = Proxy('localhost', target_protocol="https")
        env = get_default_environ()
        res = self.cp(env, self.simulate_start_response)
        self.assertEquals(res, "Success!")
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "https")
        self.assertEquals(self.response.environ['SERVER_PORT'], "443")
        self.assertEquals(self.response.environ['HTTPS'], "on")

    def test_bad_target_protocol(self):
        """
        Tests that the Proxy class raises a ValueError if the user specified an
        invalid target_protocol
        """
        self.cp = Proxy('localhost', target_protocol="junkproto")
        env = get_default_environ()
        with self.assertRaises(ValueError):
            self.cp(env, self.simulate_start_response)

    def test_cant_fall_through_proto(self):
        """
        Tests that even odd capitolization behaves as intended in the
        target_protocol parsing.
        """
        self.cp = Proxy('localhost', target_protocol="hTTp")
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")

    def test_bad_url_scheme_from_server(self):
        """
        Tests that bad protocols from the server are caught and handled when
        the user did not specify a target_protocol.  Alternatively, tests
        that the user cannot force the use of a different protocol by fussing
        with class innards.
        """
        env = get_default_environ()
        env['wsgi.url_scheme'] = "somejunk"
        with self.assertRaises(ValueError):
            self.cp(env, self.simulate_start_response)

    def test_fix_environ_proto_odd_caps(self):
        """
        Tests that the Proxy class fixes up capitalization if the server passes
        in an oddly-capitalized protocol.
        """
        env = get_default_environ()
        env['wsgi.url_scheme'] = "hTTp"
        self.cp(env, self.simulate_start_response)
        self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")

    def test_fix_user_forced_proto_odd_caps(self):
        """
        Tests that the Proxy class behaves as intended even if the user forces
        odd protocol capitalization after the initializer.
        """
        self.cp.target_protocol = "hTTp"
        with self.assertRaises(ValueError):
            self.cp(get_default_environ(), self.simulate_start_response)

    def test_pick_port_http(self):
        """
        Tests that the appropriate port for http is picked if not specified.
        """
        self.cp = Proxy('localhost')
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(self.cp.environ['SERVER_PORT'], "80")
        self.assertEquals(self.response.environ['SERVER_PORT'], "80")

    def test_pick_port_https(self):
        """
        Tests that the appropriate port for https is used if not specified.
        """
        self.cp = Proxy('localhost')
        env = get_default_environ()
        env['wsgi.url_scheme'] = "https"
        self.cp(env, self.simulate_start_response)
        self.assertEquals(self.cp.environ['SERVER_PORT'], "443")
        self.assertEquals(self.response.environ['SERVER_PORT'], "443")

    def test_update_host_server(self):
        """
        Tests that the Proxy class properly updates the environment to target
        the remote API.
        """
        self.cp = Proxy('self.domain')
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(self.response.environ['SERVER_NAME'], "self.domain")
        self.assertEquals(self.response.environ['HTTP_HOST'], "self.domain:80")

    def test_keep_odd_port(self):
        """
        Tests that the Proxy class will not override a user-specified port.
        """
        self.cp = Proxy('localhost', '17')
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(self.response.environ['HTTP_HOST'], "localhost:17")
        self.assertEquals(self.cp.environ['SERVER_PORT'], "17")
        self.assertEquals(self.response.environ['SERVER_PORT'], "17")

    def test_add_headers(self):
        """
        Tests that user-added headers are sent in the request.
        """
        banned_headers = [("X-My-Special-Header", "My-Value")]
        self.cp = Proxy('localhost', add_headers=banned_headers)
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals(banned_headers, self.response.headers)

    def test_remove_bad_headers(self):
        """
        Tests that headers not allowed by the wsgiref server are stripped from
        the response.
        """
        self.cp = Proxy('localhost', add_headers=banned_headers)
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertEquals([], self.response.headers)

    def test_dont_remove_bad_headers(self):
        """
        Tests that headers are not altered if not using the wsgiref server.
        """
        self.cp = Proxy('localhost', add_headers=banned_headers)
        env = get_default_environ()
        env['SERVER_SOFTWARE'] = "Not wsgiref"
        self.cp(env, self.simulate_start_response)
        self.assertEquals(banned_headers, self.response.headers)

    def test_added_ACAO_star_no_origin(self):
        """
        Tests that the appropriate ACAO header is added if allow_from is True
        and the request did not have an Origin header.
        """
        self.cp = Proxy('localhost', allow_from=True)
        self.cp(get_default_environ(), self.simulate_start_response)
        self.assertIn(("Access-Control-Allow-Origin", "*"),
                      self.response.headers)

    def test_added_ACAO_False_origin(self):
        """
        Tests that the ACAO header is not added if allow_from is False.
        """
        self.cp = Proxy('localhost', allow_from=False)
        env = get_default_environ()
        env['ORIGIN'] = "my.domain"
        self.cp(env, self.simulate_start_response)
        self.assertNotIn(("Access-Control-Allow-Origin", "my.domain"),
                         self.response.headers)

    def test_added_ACAO_True_origin(self):
        """
        Tests that the appropriate ACAO header is added if allow_from=True and
        the request has an Origin header.
        """
        self.cp = Proxy('localhost', allow_from=True)
        env = get_default_environ()
        env['ORIGIN'] = "my.domain"
        self.cp(env, self.simulate_start_response)
        self.assertIn(("Access-Control-Allow-Origin", "my.domain"),
                      self.response.headers)

    def test_added_ACAO_star_origin(self):
        """
        Tests that the correct ACAO header is added if allow_from="*" and the
        request has an origin header.
        """
        self.cp = Proxy('localhost', allow_from="*")
        env = get_default_environ()
        env['ORIGIN'] = "my.domain"
        self.cp(env, self.simulate_start_response)
        self.assertIn(("Access-Control-Allow-Origin", "my.domain"),
                      self.response.headers)

    def test_ACAO_origin_list_match(self):
        """
        Tests that the correct ACAO header is added if allow_from is a list of
        domains and an origin is specified.
        """
        self.cp = Proxy('localhost',
                        allow_from=["google.com", "my.domain", "microsoft.com"]
                        )
        env = get_default_environ()
        env['ORIGIN'] = "my.domain"
        self.cp(env, self.simulate_start_response)
        self.assertIn(("Access-Control-Allow-Origin", "my.domain"),
                      self.response.headers)

    def test_ACAO_origin_list_no_match(self):
        """
        Tests that the expected ACAO header is added if allow_from is a list
        and the origin header is present, but not one of the named domains.
        """
        self.cp = Proxy('localhost',
                        allow_from=["google.com", "microsoft.com"])
        env = get_default_environ()
        env['ORIGIN'] = "my.domain"
        self.cp(env, self.simulate_start_response)
        self.assertNotIn(("Access-Control-Allow-Origin", "my.domain"),
                         self.response.headers)
        self.assertIn(("Access-Control-Allow-Origin", "google.com"),
                      self.response.headers)

if __name__ == '__main__':
    unittest.main()
