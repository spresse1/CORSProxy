#! /usr/bin/env python

banned_headers = [
	'Connection',
	'Keep-Alive',
	'Proxy-Authenticate',
	'Proxy-Authorization',
	'TE',
	'Trailers',
	'Transfer-Encoding',
	'Upgrade',
]

from wsgiproxy.exactproxy import proxy_exact_request
from copy import deepcopy

class Proxy:
	"""A (relatively) sinple class to perform HTTP request proxying and add CORS
	headers to the response.
	
	A simple way to run this is (adjusting hosts and ports, of course):
	>>> from wsgiref.simple_server import make_server
	>>> myproxy = CORSProxy("localhost",8081,allow_from=True)
	>>> server = make_server('127.0.0.1', 8080, myproxy)
	>>> server.handle_request()
	"""
	def __init__(self, server_name, server_port=0, target_protocol = "",
		allow_from=False, auth=None, add_headers=None):
		"""
		Initializer.
		
		server_name: Required.  The name/IP of the server to connect to.
		server_port: The port to connect to.  If unset, the class will guess 
			based on whether the target is HTTP (80) or HTTPS (443)
		target_protocol: Controls whether the proxy will use HTTPS to contact 
			the target.  If set to HTTP (case insensitive), no encryption will 
			be used. If set to HTTPS, encryption will be used.  If the empty 
			string (the default), the proxy will guess, based on the method 
			used to conenct to the proxy.
		allow_from: Controls the headers that are added to the response.  If 
			False, the empty string, or the empty list, no headers will be 
			added.  If True or "*", headers will be added to allow connections 
			from any domain.  If a list, headers will be added to allow from the
			named domains only. Entries must be in the form of a URI, including 
			protocol, e.g.: "http://my-domain/".  Entries are case sensitive.
			Note that non-CORS-requests (those that do not include an Origin 
			header) will not have headers added if using a restricted list.
			However, this WILL NOT stop the request - if you wish to do so, use
			an auth function (below).
			Default: False.
		auth: A function used to authenticate clients.  Passed one 
			argument: a copy of the environment (which will include all 
			headers).  Returns True (authentication succeeded) or any other 
			value.  Returning any value except True will result in HTTP 401 
			Unauthorized being sent and no proxying of requests will be 
			performed. If a value other than true is returned, it will be
			stringified and used as the body of the response.
			See the SimpleSecretAuth class in this module for an example 
			implementation.
		add_headers: A list of ("header name", "value") tuples representing 
			additional headers to add to the response. Note that some header 
			filtering may occur AFTER these are added. Default: None
		
		Please note: The W3C includes the following statement in their CORS
			recommendations, with respect to the Access-Control-Allow-Origin
			header: "In practice the origin-list-or-null production is more 
			constrained. Rather than allowing a space-separated list of origins,
			it is either a single origin or the string "null".".  In order to 
			account for this, this proxy will inspect the origin of the request 
			and if it is in allow_from or allow_from is True or "*", the origin 
			as listed in the request will be the origin listed in the request.
			"*" may still be used if the request does not include an origin 
			header.  This is most commonly the case if not using a 
			CORS-compliant browser or if the request does not come via AJAX.
		
		Please note: The W3C remarks that no authentication data should be sent
			to a server which returns * in the Access-Control-Allow-Origin 
			header on a preflight (OPTIONS) request.  In terms of this class,
			this means you may not receive standard authentication headers under
			certain circumstances (specific browsers; javascript libraries) if
			using allow_from="*".
			In the example authentication class, a non-standard header is used 
			to work around this problem.

		For more information on the notes, please visit 
		https://www.w3.org/TR/cors/
		"""
		self.server_name=server_name
		self.server_port=server_port
		self.target_protocol=target_protocol.lower()
		self.allow_from=allow_from
		self.auth=auth
		
		#TODO: validate add_headers is the right format
		
		self.add_headers=add_headers
		
	def __call__(self, environ, start_response):
		"""
		Working function of the class.  Implements the WSGI interface to the 
		application.  That is, this does the work of proxying.
		"""
		self.environ = environ
		self.start_response= start_response
		
		# Start off by examining auth
		if self.auth is not None:
			authres = self.auth(deepcopy(environ))
			if authres is not True:
				start_response("401 Unauthorized", [])
				return str(authres)
		
		# Okay, let's look at protocol.
		if self.target_protocol != "":
			if self.target_protocol != "http" and \
					self.target_protocol != "https":
				raise ValueError("target_protocol must be http or https"
					"(case insensitive)")
			self.environ['wsgi.url_scheme'] = self.target_protocol
			if self.target_protocol == "https":
				self.environ['HTTPS']="on"
			elif 'HTTPS' in self.environ:
				del self.environ['HTTPS']
		# If the user didn't set anything, we want the same scheme to be used
		# But, force it lower case
		self.environ['wsgi.url_scheme'] = \
			self.environ['wsgi.url_scheme'].lower()
		
		# Now we can pick the appropriate target port
		if self.server_port != 0:
			self.environ['SERVER_PORT'] = str(self.server_port)
		elif self.environ['wsgi.url_scheme']=="http":
			self.environ['SERVER_PORT'] = "80"
		elif self.environ['wsgi.url_scheme']=="https":
			self.environ['SERVER_PORT'] = "443"
		else:
			# Fall through and error
			raise ValueError("WSGI Environ passed a bad url_scheme")
		
		self.environ['HTTP_HOST'] = self.server_name + ":" + \
			self.environ['SERVER_PORT']
		self.environ['SERVER_NAME'] = self.server_name
		
		return proxy_exact_request(self.environ, self.my_start_response)
	
	def my_start_response(self, status, headers):
		"""
		A wrapper around the default start_response function.  Designed to work 
		around limitations of various servers and to massage any headers 
		required in the response.
		"""
		# Start by adding user-requested headers
		if self.add_headers:
			headers+=self.add_headers
		
		# Filter for headers that will make wsgiref barf.
		# TODO: Is this needed in general?  Should it be run by default with the
		# exception of servers known to work?
		if self.environ['SERVER_SOFTWARE'].split()[0] == "WSGIServer/0.1":
			headers = [ x for x in headers if x[0] not in banned_headers ]
			
		if self.allow_from is True or self.allow_from=="*":
			if 'ORIGIN' in self.environ:
				headers.append(("Access-Control-Allow-Origin", 
					self.environ['ORIGIN']))
			else:
				headers.append(("Access-Control-Allow-Origin", "*"))
		elif self.allow_from is not False and 'ORIGIN' in self.environ:
			# Origin header sent, we look for a match
			if self.environ['ORIGIN'] in self.allow_from:
				headers.append(("Access-Control-Allow-Origin", 
					self.environ['ORIGIN']))
			else:
				# From a non-allowed origin.  Respond with a header, but 
				# include only the first allowed entry.
				headers.append(("Access-Control-Allow-Origin", 
					self.allow_from[0]))
		# else add no header
				
		return self.start_response(status, headers)
