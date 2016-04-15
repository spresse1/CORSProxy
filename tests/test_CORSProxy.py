#!/usr/bin/env python

# Unit testing is good for the soul.
import mock
import unittest
from CORSProxy import CORSProxy
from CORSProxy.CORSProxy import Proxy

class Response:
	status=""
	headers=[]
	environ={}
	
class test_CORSProxy(unittest.TestCase):
	def simulate_called(self, environ, start_response):
		self.response.environ = environ
		start_response(self.status, self.headers)
		return mock.DEFAULT
	
	def simulate_start_response(self, status, headers):
		self.response.status = status
		self.response.headers = headers
	
	def setUp(self):
		self.environ = None
		self.headers = []
		self.status = "200 OK"
		self.response = Response()
		self.mf = mock.patch('CORSProxy.CORSProxy.proxy_exact_request').start()
		self.mf.return_value="Success!"
		self.mf.side_effect = self.simulate_called
		self.cp = Proxy('localhost')
	
	def get_default_environ(self):
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
	
	def test_basic(self):
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(res, "Success!")
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
		self.assertEquals(self.response.status, "200 OK")
	
	def test_auth_true(self):
		self.cp = Proxy('localhost', auth=lambda x: True)
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEqual(self.response.status, "200 OK")
		
	def test_auth_false(self):
		self.cp = Proxy('localhost', auth=lambda x: False)
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEqual(self.response.status, "401 Unauthorized")
		
	def test_auth_message(self):
		self.cp = Proxy('localhost', 
			auth=lambda x: "My error message")
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEqual(self.response.status, "401 Unauthorized")
		self.assertEqual(res, "My error message")
	
	def test_keep_https(self):
		env = self.get_default_environ()
		env['wsgi.url_scheme'] = "https"
		env['HTTPS'] = "on"
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(res, "Success!")
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "https")
		self.assertEquals(self.response.environ['HTTPS'], "on")
	
	def test_keep_http(self):
		env = self.get_default_environ()
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(res, "Success!")
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
		self.assertNotIn('HTTPS', self.response.environ)
	
	def test_force_http_downgrade(self):
		self.cp = Proxy('localhost', target_protocol="http")
		env = self.get_default_environ()
		env['wsgi.url_scheme'] = "https"
		env['HTTPS'] = "on"
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(res, "Success!")
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
		self.assertEquals(self.response.environ['SERVER_PORT'], "80")
		self.assertNotIn('HTTPS', self.response.environ)
	
	def test_force_https_upgrade(self):
		self.cp = Proxy('localhost', target_protocol="https")
		env = self.get_default_environ()
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(res, "Success!")
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "https")
		self.assertEquals(self.response.environ['SERVER_PORT'], "443")
		self.assertEquals(self.response.environ['HTTPS'], "on")
	
	def test_bad_target_protocol(self):
		self.cp = Proxy('localhost', target_protocol="junkproto")
		env = self.get_default_environ()
		with self.assertRaises(ValueError):
			self.cp(env, self.simulate_start_response)	
	
	def test_cant_fall_through_proto(self):
		self.cp = Proxy('localhost', target_protocol="hTTp")
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
	
	def test_bad_url_scheme_from_server(self):
		env = self.get_default_environ()
		env['wsgi.url_scheme'] = "somejunk"
		with self.assertRaises(ValueError):
			self.cp(env, self.simulate_start_response)
	
	def test_fix_environ_proto_odd_caps(self):
		env = self.get_default_environ()
		env['wsgi.url_scheme'] = "hTTp"
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(self.response.environ['wsgi.url_scheme'], "http")
	
	def test_fix_user_forced_proto_odd_caps(self):
		self.cp.target_protocol = "hTTp"
		with self.assertRaises(ValueError):
			self.cp(self.get_default_environ(), self.simulate_start_response)
	
	def test_pick_port_http(self):
		self.cp = Proxy('localhost')
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(self.cp.environ['SERVER_PORT'], "80")
		self.assertEquals(self.response.environ['SERVER_PORT'], "80")
	
	def test_pick_port_https(self):
		self.cp = Proxy('localhost')
		env = self.get_default_environ()
		env['wsgi.url_scheme'] = "https"
		res = self.cp(env, self.simulate_start_response)
		self.assertEquals(self.cp.environ['SERVER_PORT'], "443")
		self.assertEquals(self.response.environ['SERVER_PORT'], "443")
	
	def test_update_host_server(self):
		self.cp = Proxy('self.domain')
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(self.response.environ['SERVER_NAME'], "self.domain")
		self.assertEquals(self.response.environ['HTTP_HOST'], "self.domain:80")
	
	def test_keep_odd_port(self):
		self.cp = Proxy('localhost', '17')
		res = self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(self.response.environ['HTTP_HOST'], "localhost:17")
		self.assertEquals(self.cp.environ['SERVER_PORT'], "17")
		self.assertEquals(self.response.environ['SERVER_PORT'], "17")
	
	def test_add_headers(self):
		hdr = [("X-My-Special-Header", "My-Value")]
		self.cp = Proxy('localhost', add_headers=hdr)
		self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals(hdr, self.response.headers)
	
	def test_remove_bad_headers(self):
		hdr = [
			("Connection", "My-Value"),
			("Keep-Alive", "False"),
			("Proxy-Authenticate", "Nope"),
			("Proxy-Authorization", "Not here"),
			('TE', "what"),
			('Trailers', "None"),
			('Transfer-Encoding', "Nothing"),
			('Upgrade', "Dont"),
		]
		self.cp = Proxy('localhost', add_headers=hdr)
		self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertEquals([], self.response.headers)
	
	def test_dont_remove_bad_headers(self):
		hdr = [
			("Connection", "My-Value"),
			("Keep-Alive", "False"),
			("Proxy-Authenticate", "Nope"),
			("Proxy-Authorization", "Not here"),
			('TE', "what"),
			('Trailers', "None"),
			('Transfer-Encoding', "Nothing"),
			('Upgrade', "Dont"),
		]
		self.cp = Proxy('localhost', add_headers=hdr)
		env = self.get_default_environ()
		env['SERVER_SOFTWARE'] = "Not wsgiref"
		self.cp(env, self.simulate_start_response)
		self.assertEquals(hdr, self.response.headers)
	
	def test_added_ACAO_star_no_origin(self):
		self.cp = Proxy('localhost', allow_from=True)
		self.cp(self.get_default_environ(), self.simulate_start_response)
		self.assertIn(("Access-Control-Allow-Origin", "*"), 
			self.response.headers)
	
	def test_added_ACAO_False_origin(self):
		self.cp = Proxy('localhost', allow_from=False)
		env = self.get_default_environ()
		env['ORIGIN'] = "my.domain"
		self.cp(env, self.simulate_start_response)
		self.assertNotIn(("Access-Control-Allow-Origin", "my.domain"), 
			self.response.headers)
	
	def test_added_ACAO_True_origin(self):
		self.cp = Proxy('localhost', allow_from=True)
		env = self.get_default_environ()
		env['ORIGIN'] = "my.domain"
		self.cp(env, self.simulate_start_response)
		self.assertIn(("Access-Control-Allow-Origin", "my.domain"), 
			self.response.headers)
	
	def test_added_ACAO_star_origin(self):
		self.cp = Proxy('localhost', allow_from="*")
		env = self.get_default_environ()
		env['ORIGIN'] = "my.domain"
		self.cp(env, self.simulate_start_response)
		self.assertIn(("Access-Control-Allow-Origin", "my.domain"), 
			self.response.headers)
	
	def test_ACAO_origin_list_match(self):
		self.cp = Proxy('localhost', 
			allow_from=["google.com", "my.domain", "microsoft.com"])
		env = self.get_default_environ()
		env['ORIGIN'] = "my.domain"
		self.cp(env, self.simulate_start_response)
		self.assertIn(("Access-Control-Allow-Origin", "my.domain"), 
			self.response.headers)
	
	def test_ACAO_origin_list_no_match(self):
		self.cp = Proxy('localhost', 
			allow_from=["google.com", "microsoft.com"])
		env = self.get_default_environ()
		env['ORIGIN'] = "my.domain"
		self.cp(env, self.simulate_start_response)
		self.assertNotIn(("Access-Control-Allow-Origin", "my.domain"), 
			self.response.headers)
		self.assertIn(("Access-Control-Allow-Origin", "google.com"), 
			self.response.headers)
		
if __name__ == '__main__':
    unittest.main()
